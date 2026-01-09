from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from .models import User, Transaction
import razorpay
import json

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def home(request):
    return render(request, 'home/index.html')

@csrf_exempt
def create_order(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            role = data.get('role')
            
            # Role-based pricing mapping
            ROLE_PRICING = {
                'job_seeker': 9900,  # ₹99 in paise
                'joiner': 14900,     # ₹149 in paise
                'part_time': 31900,  # ₹199 in paise
                'employer': 42900,   # ₹249 in paise
                'freelancer': 29900  # ₹249 in paise
            }
            
            # Validate role and get amount
            if role not in ROLE_PRICING:
                return JsonResponse({'error': 'Invalid role selected'}, status=400)
            
            amount = ROLE_PRICING[role]
            
            # Create order in Razorpay
            order_data = {
                'amount': amount,
                'currency': 'INR',
                'payment_capture': '1'  # Auto-capture payment
            }
            order = razorpay_client.order.create(order_data)
            
            return JsonResponse({
                'id': order['id'],
                'amount': order['amount'],
                'currency': order['currency'],
                'key': settings.RAZORPAY_KEY_ID  # Send key for frontend
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def handle_payment(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("Raw request data:", data)  
            
            # Verify payment signature
            params_dict = {
                'razorpay_order_id': data['razorpay_order_id'],
                'razorpay_payment_id': data['razorpay_payment_id'],
                'razorpay_signature': data['razorpay_signature']
            }
            
            try:
                razorpay_client.utility.verify_payment_signature(params_dict)
                
                # Get user data from the form
                first_name = data.get('first_name', '')
                last_name = data.get('last_name', '')
                email = data.get('email')
                phone = data.get('phone')
                user_type = data.get('user_type')
                reference_code = data.get('ref_code', '').strip() or None
                
                # Use role-based pricing from backend (more secure than trusting client data)
                ROLE_PRICING = {
                    'job_seeker': 99,
                    'joiner': 149,
                    'part_time': 319,
                    'employer': 429,
                    'freelancer': 299
                }
                amount = ROLE_PRICING.get(user_type, 0)
                
                # Create or update user and transaction in a single transaction
                with transaction.atomic():
                    # Create user if not exists, otherwise update
                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            'username': email,
                            'first_name': first_name,
                            'last_name': last_name,
                            'phone': phone,
                            'user_type': user_type,
                            'reference_code': reference_code,
                            'is_paid': True
                        }
                    )
                    print(f"User {'created' if created else 'updated'}. Reference code set to: {reference_code}")  # Debug log

                    # If user already exists, update their information
                    if not created:
                        user.first_name = first_name
                        user.last_name = last_name
                        user.phone = phone
                        user.user_type = user_type
                        if reference_code:  # Only update reference code if provided
                            user.reference_code = reference_code
                            print(f"Updating reference_code to: {reference_code}")  # Debug log
                        user.is_paid = True
                        user.save()
                    
                    # Create transaction record
                    Transaction.objects.create(
                        user=user,
                        razorpay_payment_id=data['razorpay_payment_id'],
                        razorpay_order_id=data['razorpay_order_id'],
                        razorpay_signature=data['razorpay_signature'],
                        amount=amount,
                        status='successful'
                    )
                
                # Log the user in
                user = authenticate(username=email, password=None)
                if user is not None:
                    login(request, user)
                
                return JsonResponse({
                    'status': 'success',
                    'redirect': '/success/'
                })
                
            except razorpay.errors.SignatureVerificationError:
                # Log failed transaction with correct amount
                user_type = data.get('user_type')
                ROLE_PRICING = {
                    'job_seeker': 99,
                    'joiner': 149,
                    'part_time': 319,
                    'employer': 429,
                    'freelancer': 299
                }
                failed_amount = ROLE_PRICING.get(user_type, 0)
                Transaction.objects.create(
                    razorpay_payment_id=data.get('razorpay_payment_id'),
                    razorpay_order_id=data.get('razorpay_order_id'),
                    razorpay_signature=data.get('razorpay_signature'),
                    amount=failed_amount,
                    status='failed'
                )
                return JsonResponse({'error': 'Invalid payment signature'}, status=400)
                
        except Exception as e:
            # Log any other errors with correct amount
            user_type = data.get('user_type')
            ROLE_PRICING = {
                'job_seeker': 99,
                'joiner': 149,
                'part_time': 319,
                'employer': 429,
                'freelancer': 299
            }
            failed_amount = ROLE_PRICING.get(user_type, 0)
            Transaction.objects.create(
                razorpay_payment_id=data.get('razorpay_payment_id'),
                razorpay_order_id=data.get('razorpay_order_id'),
                razorpay_signature=data.get('razorpay_signature'),
                amount=failed_amount,
                status='failed'
            )
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

# @login_required
def payment_success(request):
    return render(request, 'home/payment_success.html')

def logout_view(request):
    logout(request)
    return redirect('home')


def about(request):
    return render(request, 'home/about.html')

def services(request):
    return render(request, 'home/services.html')