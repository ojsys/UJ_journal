"""Static file storage backends."""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Manifest storage that degrades instead of taking the site down.

    The strict manifest backend raises ValueError whenever a {% static %} path
    is missing from staticfiles.json, which turns a forgotten `collectstatic`
    into a site-wide 500. Deploys here are manual (cPanel, no build step), so
    that trade is wrong for us.

    Once collectstatic has run, every path is in the manifest and this behaves
    exactly like the strict backend: hashed filenames, cached forever.
    """

    manifest_strict = False

    def stored_name(self, name):
        """Fall back to the plain URL for anything not in the manifest.

        The default non-strict behaviour hashes the file from disk, but that
        hashed copy only exists if collectstatic wrote it — so the fallback URL
        404s and the page renders unstyled. Returning the unhashed name instead
        gives WhiteNoise a file it can actually serve (uncached, since it can no
        longer prove the contents are immutable).
        """
        cleaned_name = self.clean_name(name)
        if self.hash_key(cleaned_name) in self.hashed_files:
            return super().stored_name(name)
        return cleaned_name
