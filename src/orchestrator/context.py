"""Backend-side context isolation checks for DS1.

No model output can expand a user's organization or card access.
"""

from __future__ import annotations

from .models import ActiveContext, UserIdentity


class ContextResolutionError(PermissionError):
    """Raised when the authenticated request cannot use its proposed context."""


def resolve_context(*, actor: UserIdentity, context: ActiveContext) -> ActiveContext:
    """Return a context only when it belongs to and is authorized for *actor*.

    A request with no active card is permitted for general legal questions. Any
    card-scoped request must pass both organization and explicit-card checks.
    """

    if actor.organization_id != context.organization_id:
        raise ContextResolutionError("organization mismatch")

    if context.card_id is not None and context.card_id not in actor.authorized_card_ids:
        raise ContextResolutionError("card is not authorized for this user")

    return context
