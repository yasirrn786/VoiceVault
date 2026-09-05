from app.schemas.responses import ContextAnalysis


def requested_action(context: ContextAnalysis) -> dict[str, object]:
    return {
        "type": context.action_type,
        "amount": context.amount,
        "currency": context.currency,
        "new_beneficiary": context.new_beneficiary,
    }
