class LanguageTranslations:
    """USSD language translations with corrected Chichewa"""
    
    TRANSLATIONS = {
        'en': {
            'welcome': 'WELCOME TO ECORET',
            'choose_language': 'Choose Language',
            'enter_group_code': 'Enter your Group Code:',
            'main_menu': 'Welcome {name}',
            'take_loan': 'Take a Loan',
            'deposit': 'Deposit',
            'check_balance': 'Check Balance',
            'my_info': 'My Info',
            'back': 'Back',
            'exit': 'Exit',
            
            'group_loan': 'Group Loan',
            'ecoret_loan': 'ECORET Loan',
            'loan_amount': 'Enter loan amount in MK:',
            'enter_otp': 'Enter OTP sent to your phone:',
            'loan_balance': 'Loan Balance',
            'repay_loan': 'Repay Loan',
            'repayment_amount': 'Enter repayment amount in MK:',
            'loan_request_submitted': 'Loan request submitted! Amount: MK{amount}',
            
            'pay_savings': 'Pay for Savings',
            'savings_balance': 'Savings Balance',
            'savings_amount': 'Enter savings amount in MK:',
            'savings_deposit': 'Savings deposit recorded successfully!',
            
            'deposit_options': 'Deposit Options:',
            'choose_network': 'Choose network:',
            'enter_pin': 'Enter your PIN:',
            
            'balance_options': 'Balance Options:',
            'total_balance': 'Total Balance:',
            'total_deposits': 'Total Deposits:',
            'total_withdrawals': 'Total Withdrawals:',
            
            'member_info': 'Member Information:',
            'name': 'Name',
            'phone': 'Phone',
            'group': 'Group',
            'member_since': 'Member since:',
            'thank_you': 'Thank you for using ECORET',
            
            'invalid_option': 'Invalid option. Please try again.',
            'invalid_group': 'Invalid group code. Please try again.',
            'not_registered': 'You are not registered in this group.',
            'min_amount': 'Minimum amount is MK{amount}',
            'max_amount': 'Maximum amount is MK{amount}',
            'invalid_amount': 'Invalid amount. Please enter a number.',
            'no_active_loans': 'You have no active loans.',
            'no_savings': 'You have no savings yet.',
            'otp_sent': 'OTP sent to your phone.',
            'otp_invalid': 'Invalid or expired OTP.',
            'transaction_approved': 'Transaction approved successfully!',
            'payment_pending': 'A payment request has been sent to your phone. Please complete the payment with your mobile money PIN when prompted to confirm this transaction.',
        },
        'ny': {
            'welcome': 'TAKULANDILANI KU ECORET',
            'choose_language': 'Sankhani chilankhulo',
            'enter_group_code': 'Lowetsani code ya gulu:',
            'main_menu': 'Menyu',
            'take_loan': 'Kutenga ngongole',
            'deposit': 'Kuyika ndalama',
            'check_balance': 'Onana ma shaya',
            'my_info': 'Zambiri Zanga',
            'case'
            'back': 'Bwerera',
            'exit': 'Tuluka',
            
            'group_loan': 'Ngongole ya Gulu',
            'ecoret_loan': 'Ngongole ya ECORET',
            'loan_amount': 'Lowetsani ndalama zomwe mungongole:',
            'enter_otp': 'Lowetsani OTP(numbala yachinsinsi) yomwe yatumizidwa ku foni yanu:',
            'loan_balance': 'Ndalama za ngongole',
            'repay_loan': 'Kubweza ngongole',
            'repayment_amount': 'Lowetsani ndalama zobwezera ngongole:',
            'loan_request_submitted': 'Pempho la ngongole latumizidwa! Ndalama: MK{amount}',
            
            'pay_savings': 'Kusheya ndalama',
            'savings_balance': 'Ndalama zosala kuthumba',
            'savings_amount': 'Lowetsani ndalama zomwe mukufuna kusheya:',
            'savings_deposit': 'Ndalama zasungidwa bwino!',
            
            'deposit_options': 'Kusankha Koyika Ndalama:',
            'choose_network': 'Sankhani network:',
            'enter_pin': 'Lowetsani PIN(numbala yachinsinsi) yanu:',
            
            'balance_options': 'Zosankha za Kuthumba:',
            'total_balance': 'Ndalama zonse:',
            'total_deposits': 'Ndalama zonse zosungidwa:',
            'total_withdrawals': 'Ndalama zonse zotulutsidwa:',
            
            'member_info': 'Zambiri Za Membala:',
            'name': 'Dzina',
            'phone': 'Foni',
            'group': 'Gulu',
            'member_since': 'Membala kuyambira:',
            'thank_you': 'Zikomo pogwiritsa ntchito ECORET',
            
            'invalid_option': 'Sankho lolakwika. Chonde yesaninso.',
            'invalid_group': 'Code ya gulu yolakwika. Chonde yesaninso.',
            'not_registered': 'Simunalembetsedwe mu gulu ili.',
            'min_amount': 'Ndalama zochepa ndi MK{amount}',
            'max_amount': 'Ndalama zochuluka ndi MK{amount}',
            'invalid_amount': 'Ndalama yolakwika. Chonde lowetsani nambala yoyenera.',
            'no_active_loans': 'Mulibe ngongole yomwe mukubweza.',
            'no_savings': 'Mulibe ndalama zosunga.',
            'otp_sent': 'OTP yatumizidwa pa foni yanu.',
            'otp_invalid': 'OTP yolakwika kapena yatha nthawi.',
            'transaction_approved': 'Ndalama zatumizidwa!',
            'payment_pending': 'Pempho la kulipira latumizidwa pa foni yanu. Chonde malizitsani kulipira pogwiritsa ntchito PIN yanu pamene mukupemphedwa kuti mutsimikizire transaction iyi.',
        }
    }
    
    @classmethod
    def get_text(cls, language, key, **kwargs):
        """Get translated text with formatting"""
        if language not in cls.TRANSLATIONS:
            language = 'en'
        
        translations = cls.TRANSLATIONS.get(language, {})
        text = translations.get(key, key)
        
        if kwargs and '{' in text:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        
        return text