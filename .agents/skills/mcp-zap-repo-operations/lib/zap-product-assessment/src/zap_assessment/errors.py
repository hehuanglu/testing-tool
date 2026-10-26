"""Stdlib-only common denial type for host contracts and isolated runtimes."""


class Blocked(ValueError):
    pass


class SecretLeak(Blocked):
    """Confirmed canary in a forbidden sink; retain a fail verdict and quarantine."""
