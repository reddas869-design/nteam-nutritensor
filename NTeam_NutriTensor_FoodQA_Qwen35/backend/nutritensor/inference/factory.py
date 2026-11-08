from nutritensor.core.config import Settings
from nutritensor.inference.contracts import InferenceProvider


def create_provider(settings: Settings) -> InferenceProvider:
    if settings.is_demo:
        from nutritensor.inference.demo import DemoProvider
        return DemoProvider()
    if settings.model_backend == "openai-compatible":
        from nutritensor.inference.remote import CompatibleProvider
        return CompatibleProvider(settings)
    from nutritensor.inference.transformers import TransformersProvider
    return TransformersProvider(settings)
