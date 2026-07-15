from rest_framework import serializers
from .models import Saving, SavingGoal, SavingSummary

class SavingSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    
    class Meta:
        model = Saving
        fields = [
            'id', 'group', 'group_name', 'member', 'member_name',
            'amount', 'saving_type', 'transaction_type', 'transaction_date',
            'reference_number', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'transaction_date', 'created_at', 'updated_at']

class SavingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Saving
        fields = ['member', 'amount', 'saving_type', 'transaction_type', 
                 'reference_number', 'notes']
    
    def validate(self, data):
        if data.get('amount', 0) <= 0:
            raise serializers.ValidationError('Amount must be greater than 0')
        return data

class SavingGoalSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.SerializerMethodField()
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    
    class Meta:
        model = SavingGoal
        fields = [
            'id', 'group', 'group_name', 'name', 'target_amount',
            'current_amount', 'target_date', 'description', 'is_completed',
            'progress_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_amount', 'created_at', 'updated_at']
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()

class SavingGoalCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingGoal
        fields = ['name', 'target_amount', 'target_date', 'description']
    
    def validate(self, data):
        if data.get('target_amount', 0) <= 0:
            raise serializers.ValidationError('Target amount must be greater than 0')
        return data

class SavingSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingSummary
        fields = [
            'date', 'total_deposits', 'total_withdrawals',
            'total_deposit_count', 'total_withdrawal_count'
        ]