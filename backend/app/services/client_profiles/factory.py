from .base import ClientProfile
from .happ import HappProfile
from .hiddify import HiddifyProfile
from .generic import GenericProfile


class ClientProfileFactory:

    def get_profile(
        self,
        client: str,
    ) -> ClientProfile:

        if client == "happ":
            return HappProfile()

        if client == "hiddify":
            return HiddifyProfile()

        return GenericProfile()


client_profile_factory = ClientProfileFactory()