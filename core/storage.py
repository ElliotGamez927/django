from whitenoise.storage import CompressedManifestStaticFilesStorage


class NoStrictManifestStorage(CompressedManifestStaticFilesStorage):
    """Igual que el de WhiteNoise, pero no falla si falta una entrada en el manifest."""
    manifest_strict = False