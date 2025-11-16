import razorpay
import logging
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class RazorpayService:
    """
    Service for interacting with Razorpay API
    Uses company-wide Razorpay credentials from environment variables
    """
    
    def __init__(self):
        """
        Initialize Razorpay client with API credentials from environment variables
        """
        try:
            self.api_key = os.getenv("RAZORPAY_KEY_ID")
            self.api_secret = os.getenv("RAZORPAY_KEY_SECRET")
            
            if not self.api_key or not self.api_secret:
                logger.error("Razorpay credentials not found in environment variables")
                raise ValueError("Razorpay credentials not found in environment variables")
                
            self.client = razorpay.Client(auth=(self.api_key, self.api_secret))
        except Exception as e:
            logger.error(f"Error initializing Razorpay client: {str(e)}")
            raise
    
    def create_order(
        self, 
        amount: int, 
        currency: str = "INR", 
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new order in Razorpay
        
        Args:
            amount: Amount in smallest currency unit (paise for INR)
            currency: Currency code (default: INR)
            receipt: Receipt ID (optional)
            notes: Additional notes for the order (optional)
            
        Returns:
            Dict containing order details
        """
        try:
            data = {
                "amount": amount,
                "currency": currency
            }
            
            if receipt:
                data["receipt"] = receipt
                
            if notes:
                data["notes"] = notes
                
            response = self.client.order.create(data=data)
            logger.info(f"Created Razorpay order: {response['id']}")
            return response
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {str(e)}")
            raise
    
    def verify_payment_signature(
        self,
        payment_id: str,
        order_id: str,
        signature: str
    ) -> bool:
        """
        Verify the payment signature from Razorpay
        
        Args:
            payment_id: Razorpay payment ID
            order_id: Razorpay order ID
            signature: Razorpay signature
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            data = {
                "razorpay_payment_id": payment_id,
                "razorpay_order_id": order_id,
                "razorpay_signature": signature
            }
            
            is_valid = self.client.utility.verify_payment_signature(data)
            return True  # If no exception is raised, signature is valid
        except Exception as e:
            logger.error(f"Invalid payment signature: {str(e)}")
            return False
    
    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Fetch payment details from Razorpay
        
        Args:
            payment_id: Razorpay payment ID
            
        Returns:
            Dict containing payment details
        """
        try:
            response = self.client.payment.fetch(payment_id)
            return response
        except Exception as e:
            logger.error(f"Error fetching payment details: {str(e)}")
            raise
    
    def refund_payment(
        self, 
        payment_id: str, 
        amount: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Refund a payment
        
        Args:
            payment_id: Razorpay payment ID
            amount: Amount to refund (optional, if not provided, full amount will be refunded)
            
        Returns:
            Dict containing refund details
        """
        try:
            data = {}
            if amount:
                data["amount"] = amount
                
            response = self.client.payment.refund(payment_id, data)
            logger.info(f"Refunded payment {payment_id}: {response['id']}")
            return response
        except Exception as e:
            logger.error(f"Error refunding payment: {str(e)}")
            raise
    
    def verify_webhook_signature(
        self,
        webhook_body: str,
        webhook_signature: str,
        webhook_secret: Optional[str] = None
    ) -> bool:
        """
        Verify the webhook signature from Razorpay
        
        Args:
            webhook_body: Raw webhook request body as string
            webhook_signature: Razorpay webhook signature from X-Razorpay-Signature header
            webhook_secret: Webhook secret (optional, will use from env if not provided)
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Get webhook secret from environment if not provided
            if not webhook_secret:
                webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
                
            if not webhook_secret:
                logger.error("Webhook secret not found in environment variables")
                return False
            
            # Use Razorpay utility to verify webhook signature
            return self.client.utility.verify_webhook_signature(
                webhook_body,
                webhook_signature,
                webhook_secret
            )
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    def create_customer(
        self,
        name: str,
        email: str,
        contact: Optional[str] = None,
        notes: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new customer in Razorpay
        
        Args:
            name: Customer name
            email: Customer email
            contact: Customer contact number (optional)
            notes: Additional notes for the customer (optional)
            
        Returns:
            Dict containing customer details
        """
        try:
            data = {
                "name": name,
                "email": email
            }
            
            if contact:
                data["contact"] = contact
                
            if notes:
                data["notes"] = notes
                
            response = self.client.customer.create(data=data)
            logger.info(f"Created Razorpay customer: {response['id']}")
            return response
        except Exception as e:
            logger.error(f"Error creating Razorpay customer: {str(e)}")
            raise
