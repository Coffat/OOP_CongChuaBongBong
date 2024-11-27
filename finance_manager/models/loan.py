from dataclasses import dataclass
import pandas as pd
from datetime import datetime, timedelta
from config.settings import LOANS_FILE, LOAN_PAYMENTS_FILE
import csv

@dataclass
class Loan:
    lona_id : int
    type : str #vay tien hay cho vay
    lender_name : str #ten nguoi cho vay
    borrower_name : str #ten nguoi vay
    amount : float
    interest_rate :float #so tien goc
    start_date : str
    due_date : str
    payment_period : str #thoi gian tra no
    interest_type : str #loai lai suat
    status : str = "Đang vay" #trang thai cua khoan vay
    remaining_principal : float = None #so tien goc con lai
    total_paid_principal : float = 0 #so tien goc da tra
    total_paid_interest : float = 0 #so tien lai da tra
    note : str = "" #ghi chu

    '''Khoi tao cac khoan vay'''
    def __post_init__(self):
         if self.remaining_principal is None:
            self.remaining_principal = self.amount
    
    @property
    def total_amount_due(self):
        '''Tinh tong so tien can phai tra (goc + lai)'''
        interest_info = self.calculate_interest()
        return self.remaining_principal + interest_info['accrued_interest']

    @property
    def next_payment_date(self):
        '''Ngay tra tien tiep theo'''
        interest_info = self.calculate_interest()
        return interest_info['next_payment_date']
    
    @property
    def days_overdue(self):
        '''So ngay qua han'''
        if self.status != "Quá hạn":
            return 0
        due_date = datetime.strptime(self.due_date, "%Y-%m-%d")
        today = datetime.now()
        return (today - due_date).days
    
    @classmethod
    def get_all(cls):
        '''Lay du lieu tu file csv'''
        try:
            df = pd.read_csv(LOANS_FILE)
            return [cls(**row) for _, row in df.iterrows()]
        except FileNotFoundError:
            df = pd.DataFrame(columns=['loan_id', 'type', 'lender_name', 'borrower_name', 
                                     'amount', 'interest_rate', 'start_date', 'due_date',
                                     'payment_period', 'interest_type', 'status', 
                                     'remaining_principal', 'total_paid_principal',
                                     'total_paid_interest', 'note'])
            df.to_csv(LOANS_FILE, index=False)
            return []
    
    def save(self):
        '''Luu du lieu vao file csv'''
        try:
            df = pd.read_csv(LOANS_FILE)
        except FileNotFoundError:
            df = pd.DataFrame(columns=['loan_id', 'type', 'lender_name', 'borrower_name', 
                                     'amount', 'interest_rate', 'start_date', 'due_date',
                                     'payment_period', 'interest_type', 'status', 
                                     'remaining_principal', 'total_paid_principal',
                                     'total_paid_interest', 'note'])
        
        new_data = pd.DataFrame([{
            'loan_id': self.loan_id,
            'type': self.type,
            'lender_name': self.lender_name,
            'borrower_name': self.borrower_name,
            'amount': self.amount,
            'interest_rate': self.interest_rate,
            'start_date': self.start_date,
            'due_date': self.due_date,
            'payment_period': self.payment_period,
            'interest_type': self.interest_type,
            'status': self.status,
            'remaining_principal': self.remaining_principal,
            'total_paid_principal': self.total_paid_principal,
            'total_paid_interest': self.total_paid_interest,
            'note': self.note
        }])
        
        if self.loan_id in df['loan_id'].values:
            df = df[df['loan_id'] != self.loan_id]
            df = pd.concat([df, new_data], ignore_index=True)
        else:
            df = pd.concat([df, new_data], ignore_index=True)
            
        df = df.sort_values('loan_id').reset_index(drop=True)
        df.to_csv(LOANS_FILE, index=False)

    def add_payment(self, amount, payment_date, principal_amount, interest_amount, note=""):
        '''Them thanh toan cho khoan vay'''
        payments = LoanPayment.get_all()
        new_payment_id = len(payments) + 1
        
        payment = LoanPayment(
            payment_id=new_payment_id,
            loan_id=self.loan_id,
            payment_date=payment_date,
            amount=amount,
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            note=note
        )
        
        payment.save()
        self.remaining_principal -= principal_amount
        
        # Cập nhật trạng thái khi đã trả hết
        if self.remaining_principal <= 0:
            self.status = "Đã trả"
            self.remaining_principal = 0  # Đảm bảo không âm
            
        self.save()
    
    def get_payments(self):
        '''Lay danh sach cac thanh toan cua khoan vay'''
        all_payments = LoanPayment.get_all()
        # Lọc chỉ lấy các thanh toán của khoản vay hiện tại
        loan_payments = [payment for payment in all_payments if payment.loan_id == self.loan_id]
        return loan_payments
            
    def calculate_interest(self, to_date: str = None) -> dict:
        '''
        Tinh lai suat den ngay chi dinh
        tra ve dict chua cac thong tin sau:
        - accrued_interest: Lai suat phat sinh
        - daily_interest: Lai suat theo ngay
        - days_elapsed: So ngay da qua
        - next_payment_date: Ngay tra tien tiep theo
        '''
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
            
        start = datetime.strptime(self.start_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")
        days = (end - start).days
        
        # Tính lãi suất theo ngày (lãi suất năm / 365)
        daily_rate = self.interest_rate / 100 / 365
        
        if self.interest_type == "Lãi đơn":
            accrued_interest = self.remaining_principal * daily_rate * days
            daily_interest = self.remaining_principal * daily_rate
        else:  # Lãi kép
            periods = days/365  # Số năm
            accrued_interest = self.remaining_principal * ((1 + self.interest_rate/100) ** periods - 1)
            daily_interest = self.remaining_principal * daily_rate * (1 + self.interest_rate/100) ** (periods-1/365)
        
        # Tính ngày trả tiền tiếp theo dựa vào payment_period
        if self.payment_period == "Hàng tháng":
            next_payment = start + timedelta(days=30)
        elif self.payment_period == "Hàng quý":
            next_payment = start + timedelta(days=90)
        else:  # Một lần
            next_payment = datetime.strptime(self.due_date, "%Y-%m-%d")
            
        while next_payment <= end:
            if self.payment_period == "Hàng tháng":
                next_payment += timedelta(days=30)
            elif self.payment_period == "Hàng quý":
                next_payment += timedelta(days=90)
            else:
                break
                
        return {
            'accrued_interest': round(accrued_interest, 2),
            'daily_interest': round(daily_interest, 2),
            'days_elapsed': days,
            'next_payment_date': next_payment.strftime("%Y-%m-%d")
        }
        
    def check_due_status(self):
        today = datetime.now()
        due_date = datetime.strptime(self.due_date, "%Y-%m-%d")
        
        if today > due_date and self.status == "Đang vay":
            self.status = "Quá hạn"
            self.save()
            return True
        return False
    
    @classmethod
    def delete(cls, loan_id: int):
        """Xóa khoản vay và tất cả lịch sử thanh toán của nó"""
        try:
            # Xóa khoản vay
            loans_df = pd.read_csv(LOANS_FILE)
            if loan_id in loans_df['loan_id'].values:
                # Xóa khoản vay
                loans_df = loans_df[loans_df['loan_id'] != loan_id]
                loans_df = loans_df.reset_index(drop=True)
                loans_df['loan_id'] = loans_df.index + 1
                loans_df.to_csv(LOANS_FILE, index=False)
                
                # Xóa tất cả lịch sử thanh toán của khoản vay này
                try:
                    payments_df = pd.read_csv(LOAN_PAYMENTS_FILE)
                    payments_df = payments_df[payments_df['loan_id'] != loan_id]
                    payments_df = payments_df.reset_index(drop=True)
                    payments_df['payment_id'] = payments_df.index + 1
                    payments_df.to_csv(LOAN_PAYMENTS_FILE, index=False)
                except FileNotFoundError:
                    # Nếu file thanh toán không tồn tại, bỏ qua
                    pass
                    
                return True
            return False
        except FileNotFoundError:
            return False
        
@dataclass
class LoanPayment:
    payment_id: int
    loan_id: int
    payment_date: str
    amount: float
    principal_amount: float  # Tiền gốc
    interest_amount: float  # Tiền lãi
    note: str = ""

    def __init__(self, payment_id, loan_id, payment_date, amount, principal_amount, interest_amount, note=""):
        self.payment_id = payment_id
        self.loan_id = loan_id
        self.payment_date = payment_date
        self.amount = amount
        self.principal_amount = principal_amount
        self.interest_amount = interest_amount
        self.note = note

    def save(self):
        """Lưu thanh toán vào file CSV"""
        payments = self.get_all()
        
        # Nếu payment_id đã tồn tại, cập nhật
        existing_payment = next((p for p in payments if p.payment_id == self.payment_id), None)
        if existing_payment:
            payments.remove(existing_payment)
        
        payments.append(self)
        
        # Lưu vào file
        with open('finance_manager/data/loan_payments.csv', 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['payment_id', 'loan_id', 'payment_date', 'amount', 'principal_amount', 'interest_amount', 'note'])
            for payment in payments:
                writer.writerow([
                    payment.payment_id,
                    payment.loan_id,
                    payment.payment_date,
                    payment.amount,
                    payment.principal_amount,
                    payment.interest_amount,
                    payment.note
                ])

    @staticmethod
    def get_all():
        """Lấy tất cả các thanh toán từ file CSV"""
        payments = []
        try:
            with open('finance_manager/data/loan_payments.csv', 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    payment = LoanPayment(
                        payment_id=int(row['payment_id']),
                        loan_id=int(row['loan_id']),
                        payment_date=row['payment_date'],
                        amount=float(row['amount']),
                        principal_amount=float(row['principal_amount']),
                        interest_amount=float(row['interest_amount']),
                        note=row['note']
                    )
                    payments.append(payment)
        except FileNotFoundError:
            # Tạo file nếu chưa tồn tại
            with open('finance_manager/data/loan_payments.csv', 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['payment_id', 'loan_id', 'payment_date', 'amount', 'principal_amount', 'interest_amount', 'note'])
        
        return payments