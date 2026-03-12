from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    age = models.PositiveIntegerField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return self.email


class OTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.code}"


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.otp}"


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
    sleep_schedule = models.CharField(max_length=20, choices=SLEEP_CHOICES)
    cleanliness = models.CharField(max_length=20, choices=CLEANLINESS_CHOICES)
    social_interaction = models.CharField(max_length=20, choices=SOCIAL_CHOICES)

    def __str__(self):
        return self.user.email


class UserBudgetLocation(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    monthly_budget = models.DecimalField(max_digits=10, decimal_places=2)
    preferred_city = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email


class MatchResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="matches")
    matched_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="matched_users")
    compatibility_score = models.IntegerField()
    ai_explanation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} matched with {self.matched_user.email}"


class UserProfile(models.Model):
    ROOM_STATUS_CHOICES = [
        ("HAS_ROOM", "Has Room"),
        ("SEEKING_ROOM", "Seeking Room"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    room_status = models.CharField(max_length=20, choices=ROOM_STATUS_CHOICES, default="SEEKING_ROOM")
    photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)

    about_me = models.TextField(blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True, null=True)
    target_area = models.CharField(max_length=100, blank=True, null=True)
    budget_range = models.CharField(max_length=100, blank=True, null=True)
    move_in_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.user.email


class FavoriteMatch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    matched_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorited_users",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "matched_user")

    def __str__(self):
        return f"{self.user.email} favorited {self.matched_user.email}"


class GroupChat(models.Model):
    created_for = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_group_chats",
    )
    group_name = models.CharField(max_length=255)
    harmony_score = models.IntegerField(default=0)
    target_location = models.CharField(max_length=255, blank=True, null=True)
    compatibility_report = models.TextField(blank=True, null=True)
    is_muted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.group_name


class GroupChatMember(models.Model):
    chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    age = models.PositiveIntegerField(blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    photo = models.ImageField(upload_to="group_chat_members/", blank=True, null=True)

    class Meta:
        unique_together = ("chat", "user")

    def __str__(self):
        return f"{self.full_name} in {self.chat.group_name}"


class GroupChatMessage(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ("TEXT", "Text"),
        ("ROOM_SHARE", "Room Share"),
        ("IMAGE", "Image"),
    ]

    IMAGE_SOURCE_CHOICES = [
        ("gallery", "Gallery"),
        ("camera", "Camera"),
    ]

    chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    sender_name = models.CharField(max_length=100)
    is_current_user = models.BooleanField(default=False)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default="TEXT")
    content = models.TextField(blank=True, null=True)

    image = models.ImageField(upload_to="group_chat_images/", blank=True, null=True)
    image_source = models.CharField(max_length=20, choices=IMAGE_SOURCE_CHOICES, blank=True, null=True)

    room_title = models.CharField(max_length=255, blank=True, null=True)
    room_price = models.CharField(max_length=100, blank=True, null=True)
    room_beds = models.CharField(max_length=50, blank=True, null=True)
    room_baths = models.CharField(max_length=50, blank=True, null=True)
    schedule_tour_label = models.CharField(max_length=50, default="Schedule Tour")
    book_room_label = models.CharField(max_length=50, default="Book Room")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender_name}: {self.message_type}"


class RoomTourSchedule(models.Model):
    STATUS_CHOICES = [
        ("CONFIRMED", "Confirmed"),
        ("CANCELLED", "Cancelled"),
    ]

    chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name="tour_schedules")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room_title = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    selected_date = models.DateField()
    selected_time = models.CharField(max_length=50)
    meeting_point = models.CharField(max_length=255, default="Main Entrance of the building")
    pro_tip = models.TextField(default="Bring your ID and any questions you have for the landlord.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="CONFIRMED")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.room_title} - {self.selected_date} {self.selected_time}"


class RoomBooking(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ("CONFIRMED", "Confirmed"),
        ("PENDING", "Pending"),
        ("FAILED", "Failed"),
    ]

    chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name="room_bookings")
    booked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room_title = models.CharField(max_length=255)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    service_fee = models.DecimalField(max_digits=10, decimal_places=2)
    total_due_now = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method_last4 = models.CharField(max_length=4)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="CONFIRMED")
    next_steps = models.TextField(
        default="Check your email for the digital lease.\nSchedule your move-in date in the chat.\nConnect with your new roommates!"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.room_title} booked by {self.booked_by.email}"


class DirectChat(models.Model):
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="direct_chats_as_user1")
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="direct_chats_as_user2")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user1", "user2")

    def __str__(self):
        return f"{self.user1.email} - {self.user2.email}"


class DirectChatMessage(models.Model):
    chat = models.ForeignKey(DirectChat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sender_name = models.CharField(max_length=100)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender_name}: {self.content[:30]}"


class UserAccountSettings(models.Model):
    LANGUAGE_CHOICES = [
        ("English (US)", "English (US)"),
        ("English (UK)", "English (UK)"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notifications_enabled = models.BooleanField(default=True)
    language = models.CharField(max_length=50, choices=LANGUAGE_CHOICES, default="English (US)")
    privacy_settings = models.CharField(max_length=100, default="Standard")

    def __str__(self):
        return f"Settings - {self.user.email}"


class AppNotification(models.Model):
    NOTIFICATION_TYPES = [
        ("PROFILE", "Profile"),
        ("ACCOUNT", "Account"),
        ("ROOM", "Room"),
        ("CHAT", "Chat"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="app_notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default="PROFILE")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.title}"


class ListedRoom(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listed_rooms")
    apartment_title = models.CharField(max_length=255)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.apartment_title} - {self.user.email}"


class ListedRoomPhoto(models.Model):
    room = models.ForeignKey(ListedRoom, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="listed_rooms/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.room.apartment_title}"