from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(email=email, password=password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class OTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OTP for {self.user.email}"


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Password Reset OTP for {self.user.email}"


class UserLifestyle(models.Model):
    SLEEP_CHOICES = [
        ("Early Bird", "Early Bird"),
        ("Night Owl", "Night Owl"),
        ("Balanced", "Balanced"),
    ]

    CLEANLINESS_CHOICES = [
        ("Minimalist", "Minimalist"),
        ("Organized", "Organized"),
        ("Relaxed", "Relaxed"),
    ]

    SOCIAL_CHOICES = [
        ("Introvert", "Introvert"),
        ("Extrovert", "Extrovert"),
        ("Moderate", "Moderate"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sleep_schedule = models.CharField(max_length=20, choices=SLEEP_CHOICES, default="Balanced")
    cleanliness = models.CharField(max_length=20, choices=CLEANLINESS_CHOICES, default="Organized")
    social_interaction = models.CharField(max_length=20, choices=SOCIAL_CHOICES, default="Moderate")

    def __str__(self):
        return self.user.email


class UserBudgetLocation(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    monthly_budget = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)
    preferred_city = models.CharField(max_length=255, default="Chennai")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email


class UserProfile(models.Model):
    ROOM_STATUS_CHOICES = [
        ("HAS_ROOM", "Has Room"),
        ("SEEKING_ROOM", "Seeking Room"),
    ]

    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100, default="Unknown")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    room_status = models.CharField(
        max_length=20,
        choices=ROOM_STATUS_CHOICES,
        default="SEEKING_ROOM"
    )

    photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)

    about_me = models.TextField(blank=True, null=True)
    target_area = models.CharField(max_length=255, blank=True, null=True)
    budget_range = models.CharField(max_length=100, blank=True, null=True)
    move_in_date = models.DateField(blank=True, null=True)

    saved_rooms = models.IntegerField(default=0)
    trust_score = models.IntegerField(default=98)
    bookings = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email


class MatchResult(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="matches"
    )
    matched_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="matched_users"
    )
    compatibility_score = models.IntegerField(default=0)
    ai_explanation = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} matched with {self.matched_user.email}"


class FavoriteMatch(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_matches"
    )
    matched_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "matched_user")

    def __str__(self):
        return f"{self.user.email} -> {self.matched_user.email}"


class GroupChat(models.Model):
    created_for = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_group_chats"
    )
    group_name = models.CharField(max_length=255)
    harmony_score = models.IntegerField(default=100)
    target_location = models.CharField(max_length=255, blank=True, null=True)
    compatibility_report = models.TextField(blank=True, null=True)
    is_muted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.group_name


class GroupChatMember(models.Model):
    chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    photo = models.ImageField(upload_to="group_members/", blank=True, null=True)

    def __str__(self):
        return f"{self.chat.group_name} - {self.user.email}"


class GroupChatMessage(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ("TEXT", "Text"),
        ("IMAGE", "Image"),
        ("ROOM_SHARE", "Room Share"),
    ]

    chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name="chat_messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    sender_name = models.CharField(max_length=100)
    is_current_user = models.BooleanField(default=False)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default="TEXT")
    content = models.TextField(blank=True, null=True)

    image = models.ImageField(upload_to="group_chat_images/", blank=True, null=True)
    image_source = models.CharField(max_length=20, blank=True, null=True)

    room_title = models.CharField(max_length=255, blank=True, null=True)
    room_price = models.CharField(max_length=100, blank=True, null=True)
    room_beds = models.CharField(max_length=50, blank=True, null=True)
    room_baths = models.CharField(max_length=50, blank=True, null=True)
    schedule_tour_label = models.CharField(max_length=100, default="Schedule Tour")
    book_room_label = models.CharField(max_length=100, default="Book Room")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender_name} - {self.message_type}"


class RoomTourSchedule(models.Model):
    STATUS_CHOICES = [
        ("CONFIRMED", "Confirmed"),
        ("PENDING", "Pending"),
    ]

    chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room_title = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    selected_date = models.DateField()
    selected_time = models.CharField(max_length=50)
    meeting_point = models.CharField(max_length=255, blank=True, null=True)
    pro_tip = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="CONFIRMED")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.room_title


class RoomBooking(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ("CONFIRMED", "Confirmed"),
        ("PENDING", "Pending"),
    ]

    chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE)
    booked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room_title = models.CharField(max_length=255)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    service_fee = models.DecimalField(max_digits=10, decimal_places=2)
    total_due_now = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method_last4 = models.CharField(max_length=10)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="CONFIRMED")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.room_title


class DirectChat(models.Model):
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="direct_chat_user1"
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="direct_chat_user2"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user1", "user2")

    def __str__(self):
        return f"{self.user1.email} & {self.user2.email}"


class DirectChatMessage(models.Model):
    chat = models.ForeignKey(DirectChat, on_delete=models.CASCADE, related_name="direct_messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sender_name = models.CharField(max_length=100)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.sender_name


class UserAccountSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notifications_enabled = models.BooleanField(default=True)
    language = models.CharField(max_length=50, default="English (US)")
    privacy_settings = models.CharField(max_length=100, default="Default")

    def __str__(self):
        return self.user.email


class AppNotification(models.Model):
    TYPE_CHOICES = [
        ("PROFILE", "Profile"),
        ("ACCOUNT", "Account"),
        ("ROOM", "Room"),
        ("CHAT", "Chat"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="PROFILE")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ListedRoom(models.Model):
    STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("SOLD_OUT", "Sold Out"),
    ]

    BATHROOM_CHOICES = [
        ("PRIVATE_BATH", "Private Bath"),
        ("SHARED_BATH", "Shared Bath"),
    ]

    ENTRY_CHOICES = [
        ("KEYLESS", "Keyless"),
        ("KEY_ENTRY", "Key Entry"),
        ("SECURITY_DESK", "Security Desk"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listed_rooms"
    )
    apartment_title = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="AVAILABLE")
    bathroom_type = models.CharField(max_length=20, choices=BATHROOM_CHOICES, default="PRIVATE_BATH")
    roommate_count = models.PositiveIntegerField(default=1)
    entry_type = models.CharField(max_length=20, choices=ENTRY_CHOICES, default="KEYLESS")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.apartment_title


class ListedRoomPhoto(models.Model):
    room = models.ForeignKey(ListedRoom, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="listed_rooms/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.room.apartment_title}"


class RoomShareRequest(models.Model):
    DURATION_CHOICES = [
        ("3 Months", "3 Months"),
        ("6 Months", "6 Months"),
        ("9 Months", "9 Months"),
        ("12 Months", "12 Months"),
        ("18 Months", "18 Months"),
        ("24+ Months", "24+ Months"),
    ]

    EMPLOYMENT_CHOICES = [
        ("Full-time", "Full-time"),
        ("Part-time", "Part-time"),
        ("Student", "Student"),
        ("Freelance", "Freelance"),
        ("Unemployed", "Unemployed"),
    ]

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    room = models.ForeignKey(ListedRoom, on_delete=models.CASCADE, related_name="share_requests")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_share_requests"
    )
    room_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_share_requests"
    )

    intro_message = models.TextField(blank=True, null=True)
    preferred_move_in_date = models.DateField(blank=True, null=True)
    duration_of_stay = models.CharField(max_length=20, choices=DURATION_CHOICES, blank=True, null=True)
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES, blank=True, null=True)

    ai_background_check_completed = models.BooleanField(default=True)
    identity_document = models.FileField(upload_to="identity_docs/", blank=True, null=True)
    identity_upload_source = models.CharField(max_length=20, blank=True, null=True)
    identity_verified = models.BooleanField(default=False)

    your_share_monthly = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    group_security_deposit = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    total_move_in = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("room", "requester")

    def __str__(self):
        return f"{self.requester.email} -> {self.room.apartment_title}"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class BookingHistory(models.Model):
    STATUS_CHOICES = [
        ("CONFIRMED", "Confirmed"),
        ("PENDING", "Pending"),
        ("CANCELLED", "Cancelled"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room_title = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    booking_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="CONFIRMED")

    def __str__(self):
        return f"{self.user.email} - {self.room_title}"


class Room(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="rooms/", null=True, blank=True)

    def __str__(self):
        return self.title