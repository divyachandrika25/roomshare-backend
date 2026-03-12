from datetime import timedelta
import random
from collections import Counter
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import (
    OTP,
    PasswordResetOTP,
    UserLifestyle,
    UserBudgetLocation,
    MatchResult,
    UserProfile,
    FavoriteMatch,
    GroupChat,
    GroupChatMember,
    GroupChatMessage,
    RoomTourSchedule,
    RoomBooking,
    DirectChat,
    DirectChatMessage,
    UserAccountSettings,
    AppNotification,
    ListedRoom,
    ListedRoomPhoto,
)

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    VerifyOTPSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    UserLifestyleSerializer,
    UserBudgetLocationSerializer,
    UserProfileSerializer,
    UserProfileCreateUpdateSerializer,
    UserProfileDataSerializer,
    MatchResultSerializer,
    DiscoverRoommateSerializer,
    RoommateProfileDetailSerializer,
    UserAccountSettingsSerializer,
    ListedRoomSerializer,
    AppNotificationSerializer,
)

User = get_user_model()


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(email, otp_code, subject_text):
    send_mail(
        subject_text,
        f"Your OTP is: {otp_code}",
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=False,
    )


def create_notification(user, title, message, notification_type="PROFILE"):
    AppNotification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
    )


def get_or_create_account_settings(user):
    settings_obj, _ = UserAccountSettings.objects.get_or_create(user=user)
    return settings_obj


def _get_user_profile(user):
    return UserProfile.objects.filter(user=user).first()


def _get_user_lifestyle(user):
    return UserLifestyle.objects.filter(user=user).first()


def _get_user_budget(user):
    return UserBudgetLocation.objects.filter(user=user).first()


def _display_name(user):
    profile = _get_user_profile(user)
    if profile and profile.full_name:
        return profile.full_name

    full_name = " ".join(
        filter(
            None,
            [
                getattr(user, "first_name", ""),
                getattr(user, "middle_name", ""),
                getattr(user, "last_name", ""),
            ],
        )
    ).strip()

    return full_name if full_name else user.email


def _member_photo_url(user, request):
    profile = _get_user_profile(user)
    if profile and profile.photo:
        return request.build_absolute_uri(profile.photo.url)
    return None


def _format_budget(value):
    if value is None:
        return None
    try:
        return f"${int(float(value)):,}"
    except Exception:
        return str(value)


def _format_currency_decimal(value):
    try:
        return f"${Decimal(value):,.2f}"
    except Exception:
        return str(value)


def _safe_pair(user_a, user_b):
    if user_a.id < user_b.id:
        return user_a, user_b
    return user_b, user_a


def calculate_match_score(current_user, other_user):
    score = 0
    reasons = []

    try:
        current_lifestyle = UserLifestyle.objects.get(user=current_user)
        other_lifestyle = UserLifestyle.objects.get(user=other_user)
    except UserLifestyle.DoesNotExist:
        current_lifestyle = None
        other_lifestyle = None

    try:
        current_budget = UserBudgetLocation.objects.get(user=current_user)
        other_budget = UserBudgetLocation.objects.get(user=other_user)
    except UserBudgetLocation.DoesNotExist:
        current_budget = None
        other_budget = None

    if current_lifestyle and other_lifestyle:
        if current_lifestyle.cleanliness == other_lifestyle.cleanliness:
            score += 30
            reasons.append("Same cleanliness preference")

        if current_lifestyle.sleep_schedule == other_lifestyle.sleep_schedule:
            score += 30
            reasons.append("Same sleep schedule")

        if current_lifestyle.social_interaction == other_lifestyle.social_interaction:
            score += 20
            reasons.append("Same social interaction style")

    if current_budget and other_budget:
        if current_budget.preferred_city.strip().lower() == other_budget.preferred_city.strip().lower():
            score += 20
            reasons.append("Preferred city matches")

        budget_gap = abs(float(current_budget.monthly_budget) - float(other_budget.monthly_budget))
        if budget_gap <= 2000:
            score += 20
            reasons.append("Budget is compatible")
        elif budget_gap <= 5000:
            score += 10
            reasons.append("Budget is close")

    return score, reasons


def generate_ai_matches(current_user):
    MatchResult.objects.filter(user=current_user).delete()
    users = User.objects.exclude(id=current_user.id)

    for other_user in users:
        if not UserProfile.objects.filter(user=other_user).exists():
            continue
        if not UserLifestyle.objects.filter(user=other_user).exists():
            continue
        if not UserBudgetLocation.objects.filter(user=other_user).exists():
            continue

        score, reasons = calculate_match_score(current_user, other_user)

        if score > 0:
            MatchResult.objects.create(
                user=current_user,
                matched_user=other_user,
                compatibility_score=score,
                ai_explanation=", ".join(reasons) if reasons else "Compatible profile",
            )


def _member_tags(lifestyle):
    tags = []
    if not lifestyle:
        return tags

    if lifestyle.cleanliness:
        tags.append(lifestyle.cleanliness.upper())
    if lifestyle.social_interaction:
        tags.append(lifestyle.social_interaction.upper())
    if len(tags) < 2 and lifestyle.sleep_schedule:
        tags.append(lifestyle.sleep_schedule.upper())

    return tags[:2]


def _most_common_value(values):
    filtered = [v for v in values if v]
    if not filtered:
        return None, 0
    return Counter(filtered).most_common(1)[0]


def _build_group_insight(member_users):
    lifestyles = [_get_user_lifestyle(user) for user in member_users]

    sleep_values = [life.sleep_schedule for life in lifestyles if life]
    clean_values = [life.cleanliness for life in lifestyles if life]
    social_values = [life.social_interaction for life in lifestyles if life]

    common_sleep, sleep_count = _most_common_value(sleep_values)
    common_clean, clean_count = _most_common_value(clean_values)
    common_social, social_count = _most_common_value(social_values)

    reasons = []

    if sleep_count >= 2 and common_sleep:
        reasons.append(f"shared {common_sleep.lower()} routines")
    if clean_count >= 2 and common_clean:
        reasons.append(f"a common preference for {common_clean.lower()} spaces")
    if social_count >= 2 and common_social:
        reasons.append(f"similar {common_social.lower()} social styles")

    if reasons:
        if len(reasons) == 1:
            text = f"This group is highly compatible due to {reasons[0]}."
        elif len(reasons) == 2:
            text = f"This group is highly compatible due to {reasons[0]} and {reasons[1]}."
        else:
            text = f"This group is highly compatible due to {reasons[0]}, {reasons[1]}, and {reasons[2]}."
    else:
        text = "This group shows good compatibility based on saved lifestyle and budget preferences."

    return {
        "title": "Key Strengths",
        "description": text,
    }


def _build_target_location(member_users):
    budgets = [_get_user_budget(user) for user in member_users]

    cities = [budget.preferred_city for budget in budgets if budget and budget.preferred_city]
    city, _ = _most_common_value(cities)

    budget_values = []
    for budget in budgets:
        if budget and budget.monthly_budget is not None:
            try:
                budget_values.append(float(budget.monthly_budget))
            except Exception:
                pass

    avg_budget = int(sum(budget_values) / len(budget_values)) if budget_values else None

    if city and avg_budget:
        description = (
            f"This area matches the group's saved city preference and an average monthly budget near "
            f"${avg_budget:,}."
        )
    elif city:
        description = "This area matches the group's saved city preference."
    else:
        description = "This location is based on the group's saved preferences."

    return {
        "name": city if city else "Location not available",
        "description": description,
    }


def _build_group_name(location_name, member_count):
    if member_count == 1:
        suffix = "Solo"
    elif member_count == 2:
        suffix = "Duo"
    else:
        suffix = "Trio"

    base_name = location_name if location_name and location_name != "Location not available" else "Harmony"
    return f"The {base_name} {suffix}"


def _build_group_members(member_users, request):
    members = []

    for user in member_users:
        profile = _get_user_profile(user)
        lifestyle = _get_user_lifestyle(user)
        budget = _get_user_budget(user)

        full_name = None
        if profile and profile.full_name:
            full_name = profile.full_name
        else:
            full_name = _display_name(user)

        members.append(
            {
                "email": user.email,
                "full_name": full_name,
                "age": profile.age if profile and profile.age is not None else getattr(user, "age", None),
                "city": budget.preferred_city if budget else getattr(user, "address", None),
                "monthly_budget": _format_budget(budget.monthly_budget) if budget else None,
                "photo": request.build_absolute_uri(profile.photo.url) if profile and profile.photo else None,
                "tags": _member_tags(lifestyle),
            }
        )

    return members


def _build_group_chat_payload(chat, request):
    members = GroupChatMember.objects.filter(chat=chat)
    messages = GroupChatMessage.objects.filter(chat=chat).order_by("created_at")

    member_avatars = []
    for member in members:
        member_avatars.append(request.build_absolute_uri(member.photo.url) if member.photo else None)

    message_data = []
    for msg in messages:
        sender_photo = _member_photo_url(msg.sender, request) if msg.sender else None

        item = {
            "id": msg.id,
            "sender_name": msg.sender_name,
            "sender_photo": sender_photo,
            "is_current_user": msg.is_current_user,
            "message_type": msg.message_type,
            "content": msg.content,
            "created_at": msg.created_at,
        }

        if msg.message_type == "IMAGE":
            item["image_url"] = request.build_absolute_uri(msg.image.url) if msg.image else None
            item["image_source"] = msg.image_source

        if msg.message_type == "ROOM_SHARE":
            item["room_card"] = {
                "title": msg.room_title,
                "price": msg.room_price,
                "beds": msg.room_beds,
                "baths": msg.room_baths,
                "schedule_tour_label": msg.schedule_tour_label,
                "book_room_label": msg.book_room_label,
            }

        message_data.append(item)

    return {
        "chat_id": chat.id,
        "chat_type": "group",
        "group_name": chat.group_name,
        "member_count": members.count(),
        "member_avatars": member_avatars,
        "menu_options": [
            {"key": "group_information", "label": "Group Information"},
            {"key": "mute_notifications", "label": "Mute Notifications", "value": chat.is_muted},
            {"key": "ai_compatibility_report", "label": "AI Compatibility Report"},
        ],
        "group_information": {
            "group_name": chat.group_name,
            "harmony_score": chat.harmony_score,
            "target_location": chat.target_location,
        },
        "ai_compatibility_report": chat.compatibility_report,
        "ai_suggestions": [
            "Share Room Details",
            "Let's meet this Saturday!",
            "What's the budget split?",
        ],
        "emoji_options": [
            "😊", "😂", "🥰", "😍", "🤩", "😎",
            "🤔", "😴", "😭", "😤", "🙌", "👍",
            "🔥", "✨", "🏠", "🎈", "💰", "📅",
        ],
        "messages": message_data,
    }


def _build_direct_chat_payload(chat, current_user, request):
    if chat.user1 == current_user:
        other_user = chat.user2
    else:
        other_user = chat.user1

    other_profile = _get_user_profile(other_user)
    messages = DirectChatMessage.objects.filter(chat=chat).order_by("created_at")

    message_data = []
    for msg in messages:
        message_data.append({
            "id": msg.id,
            "sender_email": msg.sender.email,
            "sender_name": msg.sender_name,
            "sender_photo": _member_photo_url(msg.sender, request),
            "is_current_user": msg.sender_id == current_user.id,
            "content": msg.content,
            "is_read": msg.is_read,
            "created_at": msg.created_at,
        })

    return {
        "chat_id": chat.id,
        "chat_type": "direct",
        "user": {
            "email": other_user.email,
            "full_name": other_profile.full_name if other_profile and other_profile.full_name else _display_name(other_user),
            "photo": request.build_absolute_uri(other_profile.photo.url) if other_profile and other_profile.photo else None,
        },
        "emoji_options": [
            "😊", "😂", "🥰", "😍", "🤩", "😎",
            "🤔", "😴", "😭", "😤", "🙌", "👍",
            "🔥", "✨", "🏠", "🎈", "💰", "📅",
        ],
        "messages": message_data,
    }


def _seed_group_chat_messages(chat, member_users, current_user, location_name):
    other_members = [u for u in member_users if u.id != current_user.id]
    if len(other_members) == 0:
        other_members = [current_user]

    first_member = other_members[0]
    second_member = other_members[1] if len(other_members) > 1 else other_members[0]

    GroupChatMessage.objects.create(
        chat=chat,
        sender=first_member,
        sender_name=_display_name(first_member),
        is_current_user=False,
        message_type="TEXT",
        content="Hi everyone! I'm so excited about this potential group.",
    )
    GroupChatMessage.objects.create(
        chat=chat,
        sender=second_member,
        sender_name=_display_name(second_member),
        is_current_user=False,
        message_type="TEXT",
        content=f"Me too! The location in {location_name} is perfect.",
    )
    GroupChatMessage.objects.create(
        chat=chat,
        sender=first_member,
        sender_name=_display_name(first_member),
        is_current_user=False,
        message_type="TEXT",
        content="I've checked the place, it has a great kitchen.",
    )
    GroupChatMessage.objects.create(
        chat=chat,
        sender=current_user,
        sender_name=_display_name(current_user),
        is_current_user=True,
        message_type="TEXT",
        content="Sounds great! When can we all meet?",
    )
    GroupChatMessage.objects.create(
        chat=chat,
        sender=first_member,
        sender_name=_display_name(first_member),
        is_current_user=False,
        message_type="TEXT",
        content="I'm free this Saturday afternoon! Does that work for everyone?",
    )


class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        otp_code = generate_otp()

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "is_active": False,
                "first_name": "Unknown",
                "middle_name": "",
                "last_name": "Unknown",
                "age": None,
                "address": "",
                "phone_number": "",
            }
        )

        OTP.objects.filter(user=user).delete()
        OTP.objects.create(user=user, code=otp_code)

        try:
            send_otp_email(email, otp_code, "Email Verification OTP")
            return Response({
                "success": True,
                "message": "OTP sent successfully to your email."
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "error": f"Failed to send email: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp_input = serializer.validated_data["otp"]

        try:
            user = User.objects.get(email=email)
            otp_obj = OTP.objects.filter(user=user, code=otp_input).latest("created_at")
        except (User.DoesNotExist, OTP.DoesNotExist):
            return Response({"error": "Invalid email or OTP"}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now() > otp_obj.created_at + timedelta(minutes=10):
            return Response({"error": "OTP expired"}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = True
        user.save()
        otp_obj.delete()

        return Response({
            "success": True,
            "message": "OTP verified successfully."
        }, status=status.HTTP_200_OK)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        email = request.data.get("email")
        password = request.data.get("password")
        first_name = request.data.get("first_name")
        middle_name = request.data.get("middle_name", "")
        last_name = request.data.get("last_name")
        age = request.data.get("age")
        address = request.data.get("address", "")
        phone_number = request.data.get("phone_number", "")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not password:
            return Response({"error": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not first_name:
            return Response({"error": "First name is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not last_name:
            return Response({"error": "Last name is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)

            if not user.is_active:
                return Response(
                    {"error": "Verify OTP first before registering."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if user.has_usable_password():
                return Response(
                    {"error": "User already registered with this email."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.first_name = first_name
            user.middle_name = middle_name
            user.last_name = last_name
            user.age = age if age not in [None, ""] else None
            user.address = address
            user.phone_number = phone_number
            user.set_password(password)
            user.save()

            return Response({
                "success": True,
                "message": "Registration successful.",
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "middle_name": user.middle_name,
                    "last_name": user.last_name,
                    "age": user.age,
                    "address": user.address,
                    "email": user.email,
                    "phone_number": user.phone_number,
                }
            }, status=status.HTTP_201_CREATED)

        except User.DoesNotExist:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            user.is_active = True
            user.save()

            return Response({
                "success": True,
                "message": "Registration successful.",
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "middle_name": user.middle_name,
                    "last_name": user.last_name,
                    "age": user.age,
                    "address": user.address,
                    "email": user.email,
                    "phone_number": user.phone_number,
                }
            }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        return Response({
            "success": True,
            "message": "Login successful",
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": getattr(user, "first_name", ""),
                "middle_name": getattr(user, "middle_name", ""),
                "last_name": getattr(user, "last_name", ""),
                "age": getattr(user, "age", None),
                "address": getattr(user, "address", ""),
                "phone_number": getattr(user, "phone_number", ""),
            }
        }, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        otp_code = generate_otp()

        PasswordResetOTP.objects.filter(user=user).delete()
        PasswordResetOTP.objects.create(user=user, otp=otp_code)

        try:
            send_otp_email(email, otp_code, "Password Reset OTP")
            return Response({
                "success": True,
                "message": "Password reset OTP sent successfully."
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "error": f"Failed to send email: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp_input = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        try:
            user = User.objects.get(email=email)
            otp_obj = PasswordResetOTP.objects.filter(user=user, otp=otp_input).latest("created_at")
        except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
            return Response({"error": "Invalid email or OTP"}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now() > otp_obj.created_at + timedelta(minutes=10):
            return Response({"error": "OTP expired"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        otp_obj.delete()

        return Response({
            "success": True,
            "message": "Password reset successful."
        }, status=status.HTTP_200_OK)


class UserLifestyleView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        data = {
            "sleep_schedule": request.data.get("sleep_schedule"),
            "cleanliness": request.data.get("cleanliness"),
            "social_interaction": request.data.get("social_interaction")
        }

        lifestyle_obj, created = UserLifestyle.objects.get_or_create(
            user=user,
            defaults=data
        )

        if not created:
            serializer = UserLifestyleSerializer(lifestyle_obj, data=data, partial=True)
            if serializer.is_valid():
                serializer.save(user=user)
                return Response({
                    "success": True,
                    "message": "Lifestyle data saved successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = UserLifestyleSerializer(lifestyle_obj)
        return Response({
            "success": True,
            "message": "Lifestyle data saved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class UserBudgetLocationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        data = {
            "monthly_budget": request.data.get("monthly_budget"),
            "preferred_city": request.data.get("preferred_city")
        }

        budget_obj, created = UserBudgetLocation.objects.get_or_create(
            user=user,
            defaults=data
        )

        if not created:
            serializer = UserBudgetLocationSerializer(budget_obj, data=data, partial=True)
            if serializer.is_valid():
                serializer.save(user=user)
                generate_ai_matches(user)
                return Response({
                    "success": True,
                    "message": "Budget and location data saved successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        generate_ai_matches(user)
        serializer = UserBudgetLocationSerializer(budget_obj)
        return Response({
            "success": True,
            "message": "Budget and location data saved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class UserProfileCreateUpdateView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        profile_obj, created = UserProfile.objects.get_or_create(user=user)

        data = {
            "full_name": request.data.get("full_name"),
            "age": request.data.get("age"),
            "room_status": request.data.get("room_status"),
            "about_me": request.data.get("about_me"),
            "occupation": request.data.get("occupation"),
            "target_area": request.data.get("target_area"),
            "budget_range": request.data.get("budget_range"),
            "move_in_date": request.data.get("move_in_date"),
        }

        if "photo" in request.FILES:
            data["photo"] = request.FILES["photo"]

        serializer = UserProfileCreateUpdateSerializer(profile_obj, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            create_notification(
                user,
                "Profile Updated",
                "Your profile information was updated successfully.",
                "PROFILE"
            )
            return Response({
                "success": True,
                "message": "Profile updated successfully." if not created else "Profile created successfully.",
                "data": UserProfileSerializer(user, context={"request": request}).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserProfileSerializer(user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class MatchListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        generate_ai_matches(user)
        matches = MatchResult.objects.filter(user=user).order_by("-compatibility_score")
        serializer = MatchResultSerializer(matches, many=True, context={"request": request})

        return Response({
            "success": True,
            "count": matches.count(),
            "matches": serializer.data
        }, status=status.HTTP_200_OK)


class MatchDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, match_id):
        try:
            match = MatchResult.objects.get(id=match_id)
        except MatchResult.DoesNotExist:
            return Response({"error": "Match not found"}, status=status.HTTP_404_NOT_FOUND)

        user = match.matched_user
        profile = UserProfile.objects.filter(user=user).first()
        lifestyle = UserLifestyle.objects.filter(user=user).first()
        budget = UserBudgetLocation.objects.filter(user=user).first()

        data = {
            "match_id": match.id,
            "email": user.email,
            "full_name": profile.full_name if profile and profile.full_name else _display_name(user),
            "age": profile.age if profile and profile.age is not None else getattr(user, "age", None),
            "room_status": profile.room_status if profile else None,
            "photo": request.build_absolute_uri(profile.photo.url) if profile and profile.photo else None,
            "sleep_schedule": lifestyle.sleep_schedule if lifestyle else None,
            "cleanliness": lifestyle.cleanliness if lifestyle else None,
            "social_interaction": lifestyle.social_interaction if lifestyle else None,
            "monthly_budget": str(budget.monthly_budget) if budget else None,
            "preferred_city": budget.preferred_city if budget else getattr(user, "address", None),
            "compatibility_score": match.compatibility_score,
            "ai_explanation": match.ai_explanation
        }

        return Response(data, status=status.HTTP_200_OK)


class SaveFavoriteMatchView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user_email = request.data.get("user_email")
        matched_user_email = request.data.get("matched_user_email")

        if not user_email or not matched_user_email:
            return Response({"error": "user_email and matched_user_email are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=user_email)
            matched_user = User.objects.get(email=matched_user_email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if user == matched_user:
            return Response({"error": "You cannot favorite yourself"}, status=status.HTTP_400_BAD_REQUEST)

        favorite, created = FavoriteMatch.objects.get_or_create(user=user, matched_user=matched_user)

        if created:
            return Response({"success": True, "message": "Match saved to favorites"}, status=status.HTTP_201_CREATED)

        return Response({"success": True, "message": "Match already in favorites"}, status=status.HTTP_200_OK)


class FavoriteListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        favorites = FavoriteMatch.objects.filter(user=user)

        data = []
        for fav in favorites:
            profile = UserProfile.objects.filter(user=fav.matched_user).first()

            data.append({
                "email": fav.matched_user.email,
                "name": profile.full_name if profile and profile.full_name else _display_name(fav.matched_user),
                "age": profile.age if profile and profile.age is not None else getattr(fav.matched_user, "age", None),
                "room_status": profile.room_status if profile else None,
                "photo": request.build_absolute_uri(profile.photo.url) if profile and profile.photo else None
            })

        return Response({
            "count": len(data),
            "favorites": data
        }, status=status.HTTP_200_OK)


class ViewGroupDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        try:
            current_user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        top_matches = MatchResult.objects.filter(user=current_user).order_by("-compatibility_score")[:2]
        member_users = [current_user] + [match.matched_user for match in top_matches]

        group_members = _build_group_members(member_users, request)
        score_values = [match.compatibility_score for match in top_matches]
        harmony_score = round(sum(score_values) / len(score_values)) if score_values else 100

        target_location = _build_target_location(member_users)
        group_name = _build_group_name(target_location["name"], len(member_users))
        ai_insight = _build_group_insight(member_users)

        data = {
            "group_name": group_name,
            "harmony_score": harmony_score,
            "ai_compatibility_insight": ai_insight,
            "group_members": group_members,
            "target_location": target_location,
            "group_chat_enabled": True,
        }
        return Response(data, status=status.HTTP_200_OK)


class StartGroupChatView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user_email = request.data.get("user_email")
        if not user_email:
            return Response({"error": "user_email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            current_user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        top_matches = MatchResult.objects.filter(user=current_user).order_by("-compatibility_score")[:2]
        member_users = [current_user] + [match.matched_user for match in top_matches]

        target_location = _build_target_location(member_users)
        group_name = _build_group_name(target_location["name"], len(member_users))
        ai_insight = _build_group_insight(member_users)

        chat = GroupChat.objects.filter(created_for=current_user, group_name=group_name).first()

        if not chat:
            score_values = [match.compatibility_score for match in top_matches]
            harmony_score = round(sum(score_values) / len(score_values)) if score_values else 100

            chat = GroupChat.objects.create(
                created_for=current_user,
                group_name=group_name,
                harmony_score=harmony_score,
                target_location=target_location["name"],
                compatibility_report=ai_insight["description"],
            )

            for user in member_users:
                profile = _get_user_profile(user)
                budget = _get_user_budget(user)

                GroupChatMember.objects.create(
                    chat=chat,
                    user=user,
                    full_name=profile.full_name if profile and profile.full_name else _display_name(user),
                    age=profile.age if profile and profile.age is not None else getattr(user, "age", None),
                    city=budget.preferred_city if budget else getattr(user, "address", None),
                    photo=profile.photo if profile and profile.photo else None,
                )

            _seed_group_chat_messages(chat, member_users, current_user, target_location["name"])

        payload = _build_group_chat_payload(chat, request)

        return Response({
            "success": True,
            "message": "Group chat opened successfully",
            "data": payload
        }, status=status.HTTP_200_OK)


class GroupChatDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, chat_id):
        try:
            chat = GroupChat.objects.get(id=chat_id)
        except GroupChat.DoesNotExist:
            return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(_build_group_chat_payload(chat, request), status=status.HTTP_200_OK)


class GroupChatSendMessageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        chat_id = request.data.get("chat_id")
        sender_email = request.data.get("sender_email")
        message = request.data.get("message")

        if not chat_id or not sender_email or message is None:
            return Response({"error": "chat_id, sender_email and message are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chat = GroupChat.objects.get(id=chat_id)
        except GroupChat.DoesNotExist:
            return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            sender = User.objects.get(email=sender_email)
        except User.DoesNotExist:
            return Response({"error": "Sender not found"}, status=status.HTTP_404_NOT_FOUND)

        GroupChatMessage.objects.create(
            chat=chat,
            sender=sender,
            sender_name=_display_name(sender),
            is_current_user=(sender.id == chat.created_for.id),
            message_type="TEXT",
            content=message,
        )

        return Response({
            "success": True,
            "message": "Message sent successfully",
            "data": _build_group_chat_payload(chat, request)
        }, status=status.HTTP_200_OK)


class GroupChatShareRoomDetailsView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        chat_id = request.data.get("chat_id")
        sender_email = request.data.get("sender_email")

        if not chat_id or not sender_email:
            return Response({"error": "chat_id and sender_email are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chat = GroupChat.objects.get(id=chat_id)
        except GroupChat.DoesNotExist:
            return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            sender = User.objects.get(email=sender_email)
        except User.DoesNotExist:
            return Response({"error": "Sender not found"}, status=status.HTTP_404_NOT_FOUND)

        room_title = request.data.get("room_title", "Pacific Heights Loft")
        room_price = request.data.get("room_price", "$1,450/month")
        room_beds = request.data.get("room_beds", "3 Bed")
        room_baths = request.data.get("room_baths", "2 Bath")

        GroupChatMessage.objects.create(
            chat=chat,
            sender=sender,
            sender_name=_display_name(sender),
            is_current_user=(sender.id == chat.created_for.id),
            message_type="ROOM_SHARE",
            content="I've found a great place! Here are the details:",
            room_title=room_title,
            room_price=room_price,
            room_beds=room_beds,
            room_baths=room_baths,
        )

        return Response({
            "success": True,
            "message": "Room details shared successfully",
            "data": _build_group_chat_payload(chat, request)
        }, status=status.HTTP_200_OK)


class GroupChatToggleMuteView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        chat_id = request.data.get("chat_id")
        is_muted = request.data.get("is_muted")

        if chat_id is None or is_muted is None:
            return Response({"error": "chat_id and is_muted are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chat = GroupChat.objects.get(id=chat_id)
        except GroupChat.DoesNotExist:
            return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)

        if isinstance(is_muted, str):
            chat.is_muted = is_muted.lower() == "true"
        else:
            chat.is_muted = bool(is_muted)

        chat.save()

        return Response({
            "success": True,
            "message": "Mute setting updated successfully",
            "is_muted": chat.is_muted
        }, status=status.HTTP_200_OK)


class GroupChatUploadImageView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        chat_id = request.data.get("chat_id")
        sender_email = request.data.get("sender_email")
        image_source = request.data.get("image_source")
        caption = request.data.get("caption", "")
        image = request.FILES.get("image")

        if not chat_id or not sender_email or not image:
            return Response({"error": "chat_id, sender_email and image are required"}, status=status.HTTP_400_BAD_REQUEST)

        if image_source not in ["gallery", "camera"]:
            return Response({"error": "image_source must be 'gallery' or 'camera'"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chat = GroupChat.objects.get(id=chat_id)
        except GroupChat.DoesNotExist:
            return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            sender = User.objects.get(email=sender_email)
        except User.DoesNotExist:
            return Response({"error": "Sender not found"}, status=status.HTTP_404_NOT_FOUND)

        GroupChatMessage.objects.create(
            chat=chat,
            sender=sender,
            sender_name=_display_name(sender),
            is_current_user=(sender.id == chat.created_for.id),
            message_type="IMAGE",
            content=caption,
            image=image,
            image_source=image_source,
        )

        return Response({
            "success": True,
            "message": "Image shared successfully",
            "data": _build_group_chat_payload(chat, request)
        }, status=status.HTTP_200_OK)


class GroupChatEmojiListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "success": True,
                "emojis": [
                    "😊", "😂", "🥰", "😍", "🤩", "😎",
                    "🤔", "😴", "😭", "😤", "🙌", "👍",
                    "🔥", "✨", "🏠", "🎈", "💰", "📅",
                ],
            },
            status=status.HTTP_200_OK,
        )


class ScheduleRoomTourView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        chat_id = request.data.get("chat_id")
        user_email = request.data.get("user_email")
        room_title = request.data.get("room_title")
        address = request.data.get("address")
        selected_date = request.data.get("selected_date")
        selected_time = request.data.get("selected_time")
        meeting_point = request.data.get("meeting_point", "Main Entrance of the building")
        pro_tip = request.data.get("pro_tip", "Bring your ID and any questions you have for the landlord.")

        if not all([chat_id, user_email, room_title, address, selected_date, selected_time]):
            return Response({"error": "chat_id, user_email, room_title, address, selected_date and selected_time are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chat = GroupChat.objects.get(id=chat_id)
        except GroupChat.DoesNotExist:
            return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        schedule = RoomTourSchedule.objects.create(
            chat=chat,
            requested_by=user,
            room_title=room_title,
            address=address,
            selected_date=selected_date,
            selected_time=selected_time,
            meeting_point=meeting_point,
            pro_tip=pro_tip,
            status="CONFIRMED",
        )

        GroupChatMessage.objects.create(
            chat=chat,
            sender=user,
            sender_name=_display_name(user),
            is_current_user=(user.id == chat.created_for.id),
            message_type="TEXT",
            content=f"Tour scheduled for {room_title} on {selected_date} at {selected_time}.",
        )

        return Response(
            {
                "success": True,
                "message": "Tour scheduled successfully",
                "data": {
                    "schedule_id": schedule.id,
                    "room_title": schedule.room_title,
                    "address": schedule.address,
                    "selected_date": str(schedule.selected_date),
                    "selected_time": schedule.selected_time,
                    "meeting_point": schedule.meeting_point,
                    "pro_tip": schedule.pro_tip,
                    "status": schedule.status,
                    "confirmation_title": "Tour Scheduled!",
                    "confirmation_message": f"Your tour for {schedule.room_title} has been confirmed. A notification has been sent to your group.",
                    "back_button_text": "Back to Group Chat",
                },
            },
            status=status.HTTP_201_CREATED,
        )


class RoomTourDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, schedule_id):
        try:
            schedule = RoomTourSchedule.objects.get(id=schedule_id)
        except RoomTourSchedule.DoesNotExist:
            return Response({"error": "Tour schedule not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "schedule_id": schedule.id,
                "room_title": schedule.room_title,
                "address": schedule.address,
                "selected_date": str(schedule.selected_date),
                "selected_time": schedule.selected_time,
                "meeting_point": schedule.meeting_point,
                "pro_tip": schedule.pro_tip,
                "status": schedule.status,
            },
            status=status.HTTP_200_OK,
        )


class ConfirmRoomBookingView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        chat_id = request.data.get("chat_id")
        user_email = request.data.get("user_email")
        room_title = request.data.get("room_title")
        monthly_rent = request.data.get("monthly_rent")
        security_deposit = request.data.get("security_deposit")
        service_fee = request.data.get("service_fee")
        payment_method_last4 = request.data.get("payment_method_last4")

        if not all([chat_id, user_email, room_title, monthly_rent, security_deposit, service_fee, payment_method_last4]):
            return Response({"error": "chat_id, user_email, room_title, monthly_rent, security_deposit, service_fee and payment_method_last4 are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chat = GroupChat.objects.get(id=chat_id)
        except GroupChat.DoesNotExist:
            return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        monthly_rent_decimal = Decimal(monthly_rent)
        security_deposit_decimal = Decimal(security_deposit)
        service_fee_decimal = Decimal(service_fee)
        total_due_now = monthly_rent_decimal + security_deposit_decimal + service_fee_decimal

        booking = RoomBooking.objects.create(
            chat=chat,
            booked_by=user,
            room_title=room_title,
            monthly_rent=monthly_rent_decimal,
            security_deposit=security_deposit_decimal,
            service_fee=service_fee_decimal,
            total_due_now=total_due_now,
            payment_method_last4=payment_method_last4,
            payment_status="CONFIRMED",
        )

        GroupChatMessage.objects.create(
            chat=chat,
            sender=user,
            sender_name=_display_name(user),
            is_current_user=(user.id == chat.created_for.id),
            message_type="TEXT",
            content=f"Room booked successfully for {room_title}.",
        )

        next_steps_list = [
            "Check your email for the digital lease.",
            "Schedule your move-in date in the chat.",
            "Connect with your new roommates!",
        ]

        return Response(
            {
                "success": True,
                "message": "Room booked successfully",
                "data": {
                    "booking_id": booking.id,
                    "room_title": booking.room_title,
                    "monthly_rent": _format_currency_decimal(booking.monthly_rent),
                    "security_deposit": _format_currency_decimal(booking.security_deposit),
                    "service_fee": _format_currency_decimal(booking.service_fee),
                    "total_due_now": _format_currency_decimal(booking.total_due_now),
                    "payment_method_last4": booking.payment_method_last4,
                    "payment_status": booking.payment_status,
                    "confirmation_title": "Room Booked Successfully!",
                    "confirmation_message": f"Congratulations! You and {chat.group_name} have officially secured your shared home.",
                    "next_steps": next_steps_list,
                    "back_button_text": "Back to Dashboard",
                },
            },
            status=status.HTTP_201_CREATED,
        )


class RoomBookingDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, booking_id):
        try:
            booking = RoomBooking.objects.get(id=booking_id)
        except RoomBooking.DoesNotExist:
            return Response({"error": "Room booking not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "booking_id": booking.id,
                "room_title": booking.room_title,
                "monthly_rent": _format_currency_decimal(booking.monthly_rent),
                "security_deposit": _format_currency_decimal(booking.security_deposit),
                "service_fee": _format_currency_decimal(booking.service_fee),
                "total_due_now": _format_currency_decimal(booking.total_due_now),
                "payment_method_last4": booking.payment_method_last4,
                "payment_status": booking.payment_status,
            },
            status=status.HTTP_200_OK,
        )


class DirectChatCreateOrGetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user_email = request.data.get("user_email")
        other_user_email = request.data.get("other_user_email")

        if not user_email or not other_user_email:
            return Response({"error": "user_email and other_user_email are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=user_email)
            other_user = User.objects.get(email=other_user_email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if user.id == other_user.id:
            return Response({"error": "Cannot create chat with yourself"}, status=status.HTTP_400_BAD_REQUEST)

        user1, user2 = _safe_pair(user, other_user)
        chat, created = DirectChat.objects.get_or_create(user1=user1, user2=user2)

        if created:
            DirectChatMessage.objects.create(
                chat=chat,
                sender=other_user,
                sender_name=_display_name(other_user),
                content="Hi! I received your request for the room share.",
                is_read=False,
            )

        return Response(
            {
                "success": True,
                "message": "Direct chat ready",
                "data": _build_direct_chat_payload(chat, user, request),
            },
            status=status.HTTP_200_OK,
        )


class DirectChatDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, chat_id, email):
        try:
            current_user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            chat = DirectChat.objects.get(id=chat_id)
        except DirectChat.DoesNotExist:
            return Response({"error": "Direct chat not found"}, status=status.HTTP_404_NOT_FOUND)

        if current_user.id not in [chat.user1_id, chat.user2_id]:
            return Response({"error": "You are not part of this chat"}, status=status.HTTP_403_FORBIDDEN)

        DirectChatMessage.objects.filter(chat=chat).exclude(sender=current_user).update(is_read=True)

        return Response(_build_direct_chat_payload(chat, current_user, request), status=status.HTTP_200_OK)


class DirectChatSendMessageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        chat_id = request.data.get("chat_id")
        sender_email = request.data.get("sender_email")
        message = request.data.get("message")

        if not chat_id or not sender_email or message is None:
            return Response({"error": "chat_id, sender_email and message are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chat = DirectChat.objects.get(id=chat_id)
        except DirectChat.DoesNotExist:
            return Response({"error": "Direct chat not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            sender = User.objects.get(email=sender_email)
        except User.DoesNotExist:
            return Response({"error": "Sender not found"}, status=status.HTTP_404_NOT_FOUND)

        if sender.id not in [chat.user1_id, chat.user2_id]:
            return Response({"error": "You are not part of this chat"}, status=status.HTTP_403_FORBIDDEN)

        DirectChatMessage.objects.create(
            chat=chat,
            sender=sender,
            sender_name=_display_name(sender),
            content=message,
            is_read=False,
        )

        return Response({"success": True, "message": "Direct message sent successfully"}, status=status.HTTP_200_OK)


class MessagesInboxView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        search = request.GET.get("search", "").strip().lower()

        try:
            current_user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        inbox_items = []

        group_chats = GroupChat.objects.filter(Q(created_for=current_user) | Q(members__user=current_user)).distinct()
        for chat in group_chats:
            last_message = GroupChatMessage.objects.filter(chat=chat).order_by("-created_at").first()
            if not last_message:
                continue

            if search and search not in chat.group_name.lower() and search not in (last_message.sender_name or "").lower():
                continue

            member = GroupChatMember.objects.filter(chat=chat).first()
            avatar = request.build_absolute_uri(member.photo.url) if member and member.photo else None

            unread_count = GroupChatMessage.objects.filter(chat=chat).exclude(sender=current_user).count()

            inbox_items.append({
                "conversation_type": "group",
                "conversation_id": chat.id,
                "title": chat.group_name,
                "subtitle": f"{last_message.sender_name}: {last_message.content}" if last_message.content else last_message.sender_name,
                "avatar": avatar,
                "time": last_message.created_at,
                "unread_count": unread_count,
            })

        direct_chats = DirectChat.objects.filter(Q(user1=current_user) | Q(user2=current_user)).distinct()
        for chat in direct_chats:
            other_user = chat.user2 if chat.user1_id == current_user.id else chat.user1
            other_profile = _get_user_profile(other_user)
            last_message = DirectChatMessage.objects.filter(chat=chat).order_by("-created_at").first()
            if not last_message:
                continue

            other_name = other_profile.full_name if other_profile and other_profile.full_name else _display_name(other_user)
            search_target = f"{other_name} {other_user.email} {last_message.content or ''}".lower()

            if search and search not in search_target:
                continue

            unread_count = DirectChatMessage.objects.filter(chat=chat, is_read=False).exclude(sender=current_user).count()

            inbox_items.append({
                "conversation_type": "direct",
                "conversation_id": chat.id,
                "title": other_name,
                "subtitle": last_message.content,
                "avatar": request.build_absolute_uri(other_profile.photo.url) if other_profile and other_profile.photo else None,
                "time": last_message.created_at,
                "unread_count": unread_count,
                "user_email": other_user.email,
            })

        inbox_items.sort(key=lambda x: x["time"], reverse=True)

        formatted = []
        for item in inbox_items:
            formatted.append({
                "conversation_type": item["conversation_type"],
                "conversation_id": item["conversation_id"],
                "title": item["title"],
                "subtitle": item["subtitle"],
                "avatar": item["avatar"],
                "time": item["time"],
                "unread_count": item["unread_count"],
                "user_email": item.get("user_email"),
            })

        return Response(
            {
                "success": True,
                "count": len(formatted),
                "search": search,
                "messages": formatted,
            },
            status=status.HTTP_200_OK,
        )


class ProfileDashboardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        profile, _ = UserProfile.objects.get_or_create(user=user)
        settings_obj = get_or_create_account_settings(user)
        listed_room = ListedRoom.objects.filter(user=user, is_active=True).first()

        return Response(
            {
                "success": True,
                "data": {
                    "email": user.email,
                    "first_name": getattr(user, "first_name", ""),
                    "middle_name": getattr(user, "middle_name", ""),
                    "last_name": getattr(user, "last_name", ""),
                    "age": getattr(user, "age", None),
                    "address": getattr(user, "address", ""),
                    "phone_number": getattr(user, "phone_number", ""),
                    "profile": UserProfileDataSerializer(profile, context={"request": request}).data,
                    "account_settings": UserAccountSettingsSerializer(settings_obj).data,
                    "listed_room": ListedRoomSerializer(listed_room, context={"request": request}).data if listed_room else None,
                },
            },
            status=status.HTTP_200_OK,
        )


class ProfileUpdateView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        profile, _ = UserProfile.objects.get_or_create(user=user)

        data = {
            "full_name": request.data.get("full_name"),
            "age": request.data.get("age"),
            "room_status": request.data.get("room_status"),
            "about_me": request.data.get("about_me"),
            "occupation": request.data.get("occupation"),
            "target_area": request.data.get("target_area"),
            "budget_range": request.data.get("budget_range"),
            "move_in_date": request.data.get("move_in_date"),
        }

        if "photo" in request.FILES:
            data["photo"] = request.FILES["photo"]

        serializer = UserProfileCreateUpdateSerializer(profile, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            create_notification(user, "Profile Updated", "Your profile information was updated successfully.", "PROFILE")
            return Response(
                {
                    "success": True,
                    "message": "Profile updated successfully.",
                    "data": UserProfileDataSerializer(profile, context={"request": request}).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfilePhotoUploadView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        email = request.data.get("email")
        source = request.data.get("source")
        photo = request.FILES.get("photo")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not photo:
            return Response({"error": "Photo is required"}, status=status.HTTP_400_BAD_REQUEST)

        if source not in ["camera", "gallery", None, ""]:
            return Response({"error": "source must be camera or gallery"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.photo = photo
        profile.save()

        create_notification(
            user,
            "Profile Photo Updated",
            f"Your profile photo was updated{' from ' + source if source else ''}.",
            "PROFILE"
        )

        return Response(
            {
                "success": True,
                "message": "Profile photo uploaded successfully.",
                "data": UserProfileDataSerializer(profile, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


class AccountSettingsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        settings_obj = get_or_create_account_settings(user)

        return Response(
            {
                "success": True,
                "data": UserAccountSettingsSerializer(settings_obj).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        settings_obj = get_or_create_account_settings(user)

        notifications_enabled = request.data.get("notifications_enabled")
        if notifications_enabled is not None:
            if isinstance(notifications_enabled, str):
                settings_obj.notifications_enabled = notifications_enabled.lower() == "true"
            else:
                settings_obj.notifications_enabled = bool(notifications_enabled)

        settings_obj.language = request.data.get("language", settings_obj.language)
        settings_obj.privacy_settings = request.data.get("privacy_settings", settings_obj.privacy_settings)
        settings_obj.save()

        create_notification(user, "Account Settings Updated", "Your account settings were changed.", "ACCOUNT")

        return Response(
            {
                "success": True,
                "message": "Account settings updated successfully.",
                "data": UserAccountSettingsSerializer(settings_obj).data,
            },
            status=status.HTTP_200_OK,
        )


class ChangeEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        current_email = request.data.get("current_email")
        new_email = request.data.get("new_email")

        if not current_email or not new_email:
            return Response({"error": "current_email and new_email are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=current_email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if User.objects.filter(email=new_email).exists():
            return Response({"error": "New email already exists"}, status=status.HTTP_400_BAD_REQUEST)

        user.email = new_email
        user.save()

        create_notification(user, "Email Changed", "Your email address was updated successfully.", "ACCOUNT")

        return Response(
            {
                "success": True,
                "message": "Email changed successfully.",
                "new_email": user.email,
            },
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not email or not old_password or not new_password:
            return Response({"error": "email, old_password and new_password are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user.check_password(old_password):
            return Response({"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        create_notification(user, "Password Changed", "Your password was changed successfully.", "ACCOUNT")

        return Response(
            {
                "success": True,
                "message": "Password changed successfully.",
            },
            status=status.HTTP_200_OK,
        )


class DeleteAccountView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response({"error": "email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user.check_password(password):
            return Response({"error": "Password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

        user.delete()

        return Response(
            {
                "success": True,
                "message": "Account deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )


class NotificationsListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        notifications = AppNotification.objects.filter(user=user).order_by("-created_at")
        serializer = AppNotificationSerializer(notifications, many=True)

        return Response(
            {
                "success": True,
                "count": notifications.count(),
                "notifications": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class MarkNotificationReadView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        notification_id = request.data.get("notification_id")

        if not notification_id:
            return Response({"error": "notification_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            notification = AppNotification.objects.get(id=notification_id)
        except AppNotification.DoesNotExist:
            return Response({"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)

        notification.is_read = True
        notification.save()

        return Response(
            {
                "success": True,
                "message": "Notification marked as read.",
            },
            status=status.HTTP_200_OK,
        )


class ListedRoomCreateUpdateView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @transaction.atomic
    def post(self, request):
        email = request.data.get("email")
        apartment_title = request.data.get("apartment_title")
        monthly_rent = request.data.get("monthly_rent")
        description = request.data.get("description")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not apartment_title or not monthly_rent or not description:
            return Response(
                {"error": "apartment_title, monthly_rent and description are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        room = ListedRoom.objects.filter(user=user, is_active=True).first()

        if room:
            room.apartment_title = apartment_title
            room.monthly_rent = monthly_rent
            room.description = description
            room.save()
            message_text = "Room listing updated successfully."
        else:
            room = ListedRoom.objects.create(
                user=user,
                apartment_title=apartment_title,
                monthly_rent=monthly_rent,
                description=description,
            )
            message_text = "Room listed successfully."

        if request.FILES:
            files = request.FILES.getlist("photos")
            if files:
                room.photos.all().delete()
                for file_obj in files:
                    ListedRoomPhoto.objects.create(room=room, image=file_obj)

        create_notification(user, "Room Listing Updated", message_text, "ROOM")

        return Response(
            {
                "success": True,
                "message": message_text,
                "data": ListedRoomSerializer(room, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


class ListedRoomDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        room = ListedRoom.objects.filter(user=user, is_active=True).first()
        if not room:
            return Response({"error": "No listed room found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "success": True,
                "data": ListedRoomSerializer(room, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        return Response(
            {
                "success": True,
                "message": "Logged out successfully."
            },
            status=status.HTTP_200_OK
        )


def _compat_sleep_score(current_value, other_value):
    if not current_value or not other_value:
        return 60
    if current_value == other_value:
        return 100

    pairs = {
        ("Early Bird", "Balanced"): 82,
        ("Balanced", "Early Bird"): 82,
        ("Night Owl", "Balanced"): 82,
        ("Balanced", "Night Owl"): 82,
        ("Early Bird", "Night Owl"): 45,
        ("Night Owl", "Early Bird"): 45,
    }
    return pairs.get((current_value, other_value), 65)


def _compat_cleanliness_score(current_value, other_value):
    if not current_value or not other_value:
        return 60
    if current_value == other_value:
        return 100

    pairs = {
        ("Organized", "Minimalist"): 88,
        ("Minimalist", "Organized"): 88,
        ("Organized", "Relaxed"): 60,
        ("Relaxed", "Organized"): 60,
        ("Minimalist", "Relaxed"): 70,
        ("Relaxed", "Minimalist"): 70,
    }
    return pairs.get((current_value, other_value), 68)


def _compat_social_score(current_value, other_value):
    if not current_value or not other_value:
        return 60
    if current_value == other_value:
        return 100

    pairs = {
        ("Introvert", "Moderate"): 94,
        ("Moderate", "Introvert"): 94,
        ("Extrovert", "Moderate"): 94,
        ("Moderate", "Extrovert"): 94,
        ("Introvert", "Extrovert"): 58,
        ("Extrovert", "Introvert"): 58,
    }
    return pairs.get((current_value, other_value), 72)


def _compat_budget_score(current_budget, other_budget):
    if current_budget is None or other_budget is None:
        return 60

    try:
        gap = abs(float(current_budget) - float(other_budget))
    except Exception:
        return 60

    if gap <= 100:
        return 100
    if gap <= 300:
        return 92
    if gap <= 500:
        return 84
    if gap <= 1000:
        return 72
    return 55


def calculate_detailed_compatibility(current_user, other_user):
    current_lifestyle = UserLifestyle.objects.filter(user=current_user).first()
    other_lifestyle = UserLifestyle.objects.filter(user=other_user).first()

    current_budget = UserBudgetLocation.objects.filter(user=current_user).first()
    other_budget = UserBudgetLocation.objects.filter(user=other_user).first()

    sleep_score = _compat_sleep_score(
        current_lifestyle.sleep_schedule if current_lifestyle else None,
        other_lifestyle.sleep_schedule if other_lifestyle else None,
    )
    cleanliness_score = _compat_cleanliness_score(
        current_lifestyle.cleanliness if current_lifestyle else None,
        other_lifestyle.cleanliness if other_lifestyle else None,
    )
    social_score = _compat_social_score(
        current_lifestyle.social_interaction if current_lifestyle else None,
        other_lifestyle.social_interaction if other_lifestyle else None,
    )
    budget_score = _compat_budget_score(
        current_budget.monthly_budget if current_budget else None,
        other_budget.monthly_budget if other_budget else None,
    )

    total_score = round(
        (sleep_score * 0.22) +
        (cleanliness_score * 0.30) +
        (social_score * 0.24) +
        (budget_score * 0.24)
    )

    if total_score >= 90:
        risk_title = "Minimal Risk"
        risk_message = "AI detected very strong compatibility with very low conflict risk."
    elif total_score >= 75:
        risk_title = "Low Risk"
        risk_message = "AI detected good compatibility with only minor areas to discuss."
    elif total_score >= 60:
        risk_title = "Moderate Risk"
        risk_message = "AI found some differences that should be discussed before moving in."
    else:
        risk_title = "High Risk"
        risk_message = "AI found multiple compatibility gaps that may create conflicts."

    reasons = []
    if sleep_score >= 80:
        reasons.append("compatible schedules")
    if cleanliness_score >= 85:
        reasons.append("shared cleanliness expectations")
    if social_score >= 85:
        reasons.append("similar communication and social styles")
    if budget_score >= 80:
        reasons.append("close monthly budget range")

    if reasons:
        explanation = f"AI predicts minimal risk based on {', '.join(reasons)}."
    else:
        explanation = "AI found moderate compatibility based on available lifestyle and budget data."

    return {
        "total_match": total_score,
        "explanation": explanation,
        "sleep_schedule_score": sleep_score,
        "cleanliness_score": cleanliness_score,
        "social_score": social_score,
        "budget_alignment_score": budget_score,
        "risk_title": risk_title,
        "risk_message": risk_message,
    }


class DiscoverRoommatesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        search = request.GET.get("search", "").strip().lower()

        try:
            current_user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        users = User.objects.exclude(id=current_user.id)

        filtered_users = []
        for user in users:
            profile = UserProfile.objects.filter(user=user).first()
            lifestyle = UserLifestyle.objects.filter(user=user).first()
            budget = UserBudgetLocation.objects.filter(user=user).first()

            if not profile or not lifestyle or not budget:
                continue

            full_name = profile.full_name if profile and profile.full_name else _display_name(user)
            city = budget.preferred_city if budget and budget.preferred_city else getattr(user, "address", "")
            search_text = f"{full_name} {city} {user.email}".lower()

            if search and search not in search_text:
                continue

            filtered_users.append(user)

        serializer = DiscoverRoommateSerializer(
            filtered_users,
            many=True,
            context={"request": request, "current_user": current_user}
        )

        return Response({
            "success": True,
            "count": len(serializer.data),
            "roommates": serializer.data
        }, status=status.HTTP_200_OK)


class RoommateProfileDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, current_email, target_email):
        try:
            current_user = User.objects.get(email=current_email)
        except User.DoesNotExist:
            return Response({"error": "Current user not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            target_user = User.objects.get(email=target_email)
        except User.DoesNotExist:
            return Response({"error": "Target user not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = RoommateProfileDetailSerializer(
            target_user,
            context={"request": request, "current_user": current_user}
        )

        compatibility = calculate_detailed_compatibility(current_user, target_user)

        return Response({
            "success": True,
            "data": {
                **serializer.data,
                "match_percentage": compatibility["total_match"],
                "ai_compatibility_button_label": "AI Compatibility",
                "message_button_label": "Message",
                "message_api": "/api/direct-chat/create/",
                "ai_compatibility_api": f"/api/ai-compatibility/{current_email}/{target_email}/"
            }
        }, status=status.HTTP_200_OK)


class AICompatibilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, current_email, target_email):
        try:
            current_user = User.objects.get(email=current_email)
        except User.DoesNotExist:
            return Response({"error": "Current user not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            target_user = User.objects.get(email=target_email)
        except User.DoesNotExist:
            return Response({"error": "Target user not found"}, status=status.HTTP_404_NOT_FOUND)

        profile = UserProfile.objects.filter(user=target_user).first()
        target_name = profile.full_name if profile and profile.full_name else _display_name(target_user)

        result = calculate_detailed_compatibility(current_user, target_user)

        return Response({
            "success": True,
            "data": {
                "target_email": target_user.email,
                "target_name": target_name,
                "total_match": result["total_match"],
                "headline": result["explanation"],
                "breakdown": [
                    {
                        "title": "Sleep Schedule",
                        "score": result["sleep_schedule_score"],
                        "note": "Compatible schedules" if result["sleep_schedule_score"] >= 75 else "Schedule differences may need discussion"
                    },
                    {
                        "title": "Cleanliness",
                        "score": result["cleanliness_score"],
                        "note": "Shared organized space expectations" if result["cleanliness_score"] >= 75 else "Different cleanliness habits detected"
                    },
                    {
                        "title": "Social Activity",
                        "score": result["social_score"],
                        "note": "Complementary social habits" if result["social_score"] >= 75 else "Social energy mismatch may occur"
                    },
                    {
                        "title": "Budget Alignment",
                        "score": result["budget_alignment_score"],
                        "note": "Within a close price range" if result["budget_alignment_score"] >= 75 else "Budget gap may need discussion"
                    }
                ],
                "conflict_detection": {
                    "title": result["risk_title"],
                    "message": result["risk_message"]
                }
            }
        }, status=status.HTTP_200_OK)