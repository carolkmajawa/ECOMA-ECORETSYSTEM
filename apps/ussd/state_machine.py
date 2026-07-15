"""
USSD input dispatch. Every request past the group-code step is routed
purely by session.current_menu — never by counting '*'-separated
tokens or reading a fixed position in them. This is what makes menu
depth irrelevant: a flow can grow or shrink by any number of steps
without any other flow's handling being affected.
"""
import logging

logger = logging.getLogger(__name__)


class USSDStateMachine:
    def __init__(self):
        self._handlers = {}

    def register(self, state_name):
        def decorator(fn):
            self._handlers[state_name] = fn
            return fn
        return decorator

    def dispatch(self, controller, session, group_code, user_input):
        handler = self._handlers.get(session.current_menu)
        if handler is None:
            logger.warning("No USSD state handler for menu '%s'", session.current_menu)
            return controller.handle_invalid(session)
        return handler(controller, session, group_code, user_input)


state_machine = USSDStateMachine()


@state_machine.register('main')
def _handle_main_menu(controller, session, group_code, user_input):
    return controller.handle_main_menu_choice(session, group_code, user_input)


@state_machine.register('loan_type_menu')
def _handle_loan_type_menu(controller, session, group_code, user_input):
    return controller.handle_loan_type_choice(session, group_code, user_input)


@state_machine.register('deposit_menu')
def _handle_deposit_menu(controller, session, group_code, user_input):
    return controller.handle_deposit_menu_choice(session, group_code, user_input)


@state_machine.register('balance_menu')
def _handle_balance_menu(controller, session, group_code, user_input):
    return controller.handle_balance_menu_choice(session, group_code, user_input)


@state_machine.register('loan_amount')
def _handle_loan_amount(controller, session, group_code, user_input):
    if not user_input.isdigit():
        return controller.get_invalid_amount_prompt(session, group_code)
    return controller.process_loan_amount(session, group_code, int(user_input))


@state_machine.register('otp_verification')
def _handle_otp(controller, session, group_code, user_input):
    if not (user_input.isdigit() and len(user_input) == 6):
        return controller.get_invalid_amount_prompt(session, group_code)
    return controller.handle_otp_verification(session, group_code, user_input)


@state_machine.register('repayment_amount')
def _handle_repayment(controller, session, group_code, user_input):
    if not (user_input.isdigit() and int(user_input) > 0):
        return controller.get_invalid_amount_prompt(session, group_code)
    return controller.handle_repayment_amount(session, group_code, int(user_input))


@state_machine.register('savings_amount')
def _handle_savings(controller, session, group_code, user_input):
    if not (user_input.isdigit() and int(user_input) >= 100):
        return controller.get_invalid_amount_prompt(session, group_code)
    return controller.handle_savings_amount(session, group_code, int(user_input))


@state_machine.register('cases_list')
def _handle_case_selection(controller, session, group_code, user_input):
    if not user_input.isdigit():
        return controller.handle_invalid(session)
    return controller.select_case_for_payment(session, group_code, int(user_input))


@state_machine.register('payment_pending')
def _handle_payment_pending(controller, session, group_code, user_input):
    if user_input in {'1', '01'}:
        return controller.complete_pending_mobile_payment(session)
    return controller.get_payment_pending_prompt(session)