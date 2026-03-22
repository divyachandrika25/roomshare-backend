from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model

from .models import (
    UserLifestyle,
    UserBudgetLocation,
    MatchResult,
    UserProfile,
    FavoriteMatch,
    UserAccountSettings,
    ListedRoom,
    ListedRoomPhoto,
    AppNotification,
    RoomShareRequest,
    Notification,
    BookingHistory,
    Room,
)

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=100)
    gender = serializers.ChoiceField(choices=["Male", "Female", "Other"])
    age = serializers.IntegerField(min_value=18, max_value=100)
    occupation = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    address = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def create(self, validated_data):
        full_name = validated_data.pop("full_name")
        gender = validated_data.pop("gender")
        age = validated_data.pop("age")
        occupation = validated_data.pop("occupation")
        address = validated_data.pop("address")

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"]
        )

        UserProfile.objects.create(
            user=user,
            full_name=full_name,
            gender=gender,
            age=age,
            occupation=occupation,
            address=address,
            room_status="SEEKING_ROOM",
        )

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(username=email, password=password)

        if user is None:
            try:
                user_obj = User.objects.get(email=email)
                if user_obj.check_password(password):
                    user = user_obj
            except User.DoesNotExist:
                pass

        if user is None:
            raise serializers.ValidationError("Invalid email or password")

        attrs["user"] = user
        return attrs


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=6)


class UserLifestyleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserLifestyle
        fields = "__all__"
        read_only_fields = ["user"]


class UserBudgetLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBudgetLocation
        fields = "__all__"
        read_only_fields = ["user"]


class UserProfileCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "full_name",
            "gender",
            "age",
            "occupation",
            "address",
            "room_status",
            "photo",
            "profile_photo",
            "about_me",
            "target_area",
            "budget_range",
            "move_in_date",
        ]
class UserProfileDataSerializer(serializers.ModelSerializer):
    profile_photo = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "full_name",
            "gender",
            "age",
            "address",
            "room_status",
            "photo",
            "profile_photo",
            "about_me",
            "occupation",
            "target_area",
            "budget_range",
            "move_in_date",
            "saved_rooms",
            "trust_score",
            "bookings",
            "created_at",
        ]

    def get_profile_photo(self, obj):
        request = self.context.get("request")
        if obj and obj.profile_photo:
            return request.build_absolute_uri(obj.profile_photo.url) if request else obj.profile_photo.url
        return None

    def get_photo(self, obj):
        request = self.context.get("request")
        if obj and obj.photo:
            return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url
        return None


class UserProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    profile = serializers.SerializerMethodField()
    lifestyle = serializers.SerializerMethodField()
    budget_location = serializers.SerializerMethodField()

    def get_profile(self, obj):
        profile = UserProfile.objects.filter(user=obj).first()
        return UserProfileDataSerializer(profile, context=self.context).data if profile else None

    def get_lifestyle(self, obj):
        lifestyle = UserLifestyle.objects.filter(user=obj).first()
        return UserLifestyleSerializer(lifestyle).data if lifestyle else None

    def get_budget_location(self, obj):
        budget = UserBudgetLocation.objects.filter(user=obj).first()
        return UserBudgetLocationSerializer(budget).data if budget else None


class MatchResultSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    room_status = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()

    class Meta:
        model = MatchResult
        fields = [
            "id",
            "compatibility_score",
            "ai_explanation",
            "full_name",
            "age",
            "room_status",
            "photo",
        ]

    def get_full_name(self, obj):
        profile = UserProfile.objects.filter(user=obj.matched_user).first()
        return profile.full_name if profile and profile.full_name else obj.matched_user.email

    def get_age(self, obj):
        profile = UserProfile.objects.filter(user=obj.matched_user).first()
        return profile.age if profile else None

    def get_room_status(self, obj):
        profile = UserProfile.objects.filter(user=obj.matched_user).first()
        if not profile:
            return None
        return getattr(profile, "room_status", None)

    def get_photo(self, obj):
        request = self.context.get("request")
        profile = UserProfile.objects.filter(user=obj.matched_user).first()
        if profile and getattr(profile, "profile_photo", None):
            return request.build_absolute_uri(profile.profile_photo.url) if request else profile.profile_photo.url
        if profile and getattr(profile, "photo", None):
            return request.build_absolute_uri(profile.photo.url) if request else profile.photo.url
        return None


class DiscoverRoommateSerializer(serializers.Serializer):
    email = serializers.EmailField(read_only=True)
    full_name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    monthly_budget = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    room_status = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        profile = UserProfile.objects.filter(user=obj).first()
        return profile.full_name if profile and profile.full_name else obj.email

    def get_age(self, obj):
        profile = UserProfile.objects.filter(user=obj).first()
        return profile.age if profile else None

    def get_city(self, obj):
        budget = UserBudgetLocation.objects.filter(user=obj).first()
        return budget.preferred_city if budget else None

    def get_photo(self, obj):
        request = self.context.get("request")
        profile = UserProfile.objects.filter(user=obj).first()
        if profile and getattr(profile, "profile_photo", None):
            return request.build_absolute_uri(profile.profile_photo.url) if request else profile.profile_photo.url
        if profile and getattr(profile, "photo", None):
            return request.build_absolute_uri(profile.photo.url) if request else profile.photo.url
        return None

    def get_monthly_budget(self, obj):
        budget = UserBudgetLocation.objects.filter(user=obj).first()
        if budget and budget.monthly_budget is not None:
            try:
                return f"${int(float(budget.monthly_budget)):,}"
            except Exception:
                return str(budget.monthly_budget)
        return None

    def get_tags(self, obj):
        lifestyle = UserLifestyle.objects.filter(user=obj).first()
        if not lifestyle:
            return []

        tags = []
        if lifestyle.cleanliness:
            tags.append(lifestyle.cleanliness.upper())
        if lifestyle.social_interaction:
            tags.append(lifestyle.social_interaction.upper())
        if len(tags) < 2 and lifestyle.sleep_schedule:
            tags.append(lifestyle.sleep_schedule.upper())
        return tags[:2]

    def get_room_status(self, obj):
        profile = UserProfile.objects.filter(user=obj).first()
        if not profile:
            return None
        return getattr(profile, "room_status", None)

    def get_is_favorite(self, obj):
        current_user = self.context.get("current_user")
        if not current_user:
            return False
        return FavoriteMatch.objects.filter(user=current_user, matched_user=obj).exists()


class RoommateProfileDetailSerializer(serializers.Serializer):
    email = serializers.EmailField(read_only=True)
    full_name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    room_status = serializers.SerializerMethodField()
    about_me = serializers.SerializerMethodField()
    social = serializers.SerializerMethodField()
    cleanliness = serializers.SerializerMethodField()
    sleep_schedule = serializers.SerializerMethodField()
    monthly_budget = serializers.SerializerMethodField()
    occupation = serializers.SerializerMethodField()
    target_area = serializers.SerializerMethodField()
    budget_range = serializers.SerializerMethodField()
    move_in_date = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()

    def _get_profile(self, obj):
        return UserProfile.objects.filter(user=obj).first()

    def _get_budget(self, obj):
        return UserBudgetLocation.objects.filter(user=obj).first()

    def _get_lifestyle(self, obj):
        return UserLifestyle.objects.filter(user=obj).first()

    def get_full_name(self, obj):
        profile = self._get_profile(obj)
        return profile.full_name if profile and profile.full_name else obj.email

    def get_age(self, obj):
        profile = self._get_profile(obj)
        return profile.age if profile else None

    def get_city(self, obj):
        budget = self._get_budget(obj)
        return budget.preferred_city if budget else None

    def get_photo(self, obj):
        request = self.context.get("request")
        profile = self._get_profile(obj)
        if profile and getattr(profile, "profile_photo", None):
            return request.build_absolute_uri(profile.profile_photo.url) if request else profile.profile_photo.url
        if profile and getattr(profile, "photo", None):
            return request.build_absolute_uri(profile.photo.url) if request else profile.photo.url
        return None

    def get_room_status(self, obj):
        profile = self._get_profile(obj)
        if not profile:
            return None
        return getattr(profile, "room_status", None)

    def get_about_me(self, obj):
        profile = self._get_profile(obj)
        return profile.about_me if profile else None

    def get_social(self, obj):
        lifestyle = self._get_lifestyle(obj)
        return lifestyle.social_interaction if lifestyle else None

    def get_cleanliness(self, obj):
        lifestyle = self._get_lifestyle(obj)
        return lifestyle.cleanliness if lifestyle else None

    def get_sleep_schedule(self, obj):
        lifestyle = self._get_lifestyle(obj)
        return lifestyle.sleep_schedule if lifestyle else None

    def get_monthly_budget(self, obj):
        budget = self._get_budget(obj)
        if budget and budget.monthly_budget is not None:
            try:
                return f"${int(float(budget.monthly_budget)):,}"
            except Exception:
                return str(budget.monthly_budget)
        return None

    def get_occupation(self, obj):
        profile = self._get_profile(obj)
        return profile.occupation if profile else None

    def get_target_area(self, obj):
        profile = self._get_profile(obj)
        return profile.target_area if profile else None

    def get_budget_range(self, obj):
        profile = self._get_profile(obj)
        return profile.budget_range if profile else None

    def get_move_in_date(self, obj):
        profile = self._get_profile(obj)
        return profile.move_in_date if profile else None

    def get_address(self, obj):
        profile = self._get_profile(obj)
        return profile.address if profile else None

    def get_gender(self, obj):
        profile = self._get_profile(obj)
        return profile.gender if profile else None

    def get_is_favorite(self, obj):
        current_user = self.context.get("current_user")
        if not current_user:
            return False
        return FavoriteMatch.objects.filter(user=current_user, matched_user=obj).exists()


class UserAccountSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccountSettings
        fields = "__all__"


class ListedRoomPhotoSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ListedRoomPhoto
        fields = ["id", "image"]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class ListedRoomSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()

    class Meta:
        model = ListedRoom
        fields = [
            "id",
            "apartment_title",
            "address",
            "city",
            "monthly_rent",
            "description",
            "status",
            "bathroom_type",
            "roommate_count",
            "entry_type",
            "is_active",
            "photos",
        ]

    def get_photos(self, obj):
        photos = obj.photos.all().order_by("created_at")
        return ListedRoomPhotoSerializer(photos, many=True, context=self.context).data


class AppNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppNotification
        fields = "__all__"


class HomeRoomListSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    match_percentage = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    monthly_rent_display = serializers.SerializerMethodField()

    class Meta:
        model = ListedRoom
        fields = [
            "id",
            "apartment_title",
            "address",
            "city",
            "monthly_rent",
            "monthly_rent_display",
            "status",
            "status_label",
            "bathroom_type",
            "roommate_count",
            "entry_type",
            "photos",
            "match_percentage",
        ]

    def get_photos(self, obj):
        photos = obj.photos.all().order_by("created_at")
        return ListedRoomPhotoSerializer(photos, many=True, context=self.context).data

    def get_match_percentage(self, obj):
        current_user = self.context.get("current_user")
        if not current_user:
            return 75

        budget = UserBudgetLocation.objects.filter(user=current_user).first()
        score = 70

        if budget:
            if budget.preferred_city and obj.city and budget.preferred_city.strip().lower() == obj.city.strip().lower():
                score += 15

            try:
                gap = abs(float(budget.monthly_budget) - float(obj.monthly_rent))
                if gap <= 100:
                    score += 13
                elif gap <= 300:
                    score += 10
                elif gap <= 500:
                    score += 7
                elif gap <= 1000:
                    score += 4
            except Exception:
                pass

        return min(score, 99)

    def get_status_label(self, obj):
        return "Available" if obj.status == "AVAILABLE" else "Sold Out"

    def get_monthly_rent_display(self, obj):
        try:
            return f"${int(float(obj.monthly_rent)):,}"
        except Exception:
            return str(obj.monthly_rent)


class HomeRoomDetailSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    monthly_rent_display = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    potential_roommates = serializers.SerializerMethodField()

    class Meta:
        model = ListedRoom
        fields = [
            "id",
            "apartment_title",
            "address",
            "city",
            "monthly_rent",
            "monthly_rent_display",
            "description",
            "status",
            "status_label",
            "bathroom_type",
            "roommate_count",
            "entry_type",
            "photos",
            "potential_roommates",
        ]

    def get_photos(self, obj):
        photos = obj.photos.all().order_by("created_at")
        return ListedRoomPhotoSerializer(photos, many=True, context=self.context).data

    def get_monthly_rent_display(self, obj):
        try:
            return f"${int(float(obj.monthly_rent)):,}"
        except Exception:
            return str(obj.monthly_rent)

    def get_status_label(self, obj):
        return "Available" if obj.status == "AVAILABLE" else "Sold Out"

    def get_potential_roommates(self, obj):
        current_user = self.context.get("current_user")
        request = self.context.get("request")

        if not current_user:
            return []

        matches = MatchResult.objects.filter(user=current_user).order_by("-compatibility_score")[:2]
        data = []

        for match in matches:
            matched_user = match.matched_user
            profile = UserProfile.objects.filter(user=matched_user).first()

            photo = None
            if profile and getattr(profile, "profile_photo", None):
                photo = request.build_absolute_uri(profile.profile_photo.url) if request else profile.profile_photo.url
            elif profile and getattr(profile, "photo", None):
                photo = request.build_absolute_uri(profile.photo.url) if request else profile.photo.url

            data.append({
                "email": matched_user.email,
                "full_name": profile.full_name if profile and profile.full_name else matched_user.email,
                "photo": photo,
                "match_percentage": match.compatibility_score,
            })

        return data


class RoomShareRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomShareRequest
        fields = "__all__"


class RoomShareVerificationSerializer(serializers.ModelSerializer):
    identity_document_url = serializers.SerializerMethodField()

    class Meta:
        model = RoomShareRequest
        fields = [
            "id",
            "ai_background_check_completed",
            "identity_document",
            "identity_document_url",
            "identity_upload_source",
            "identity_verified",
            "status",
        ]

    def get_identity_document_url(self, obj):
        request = self.context.get("request")
        if obj.identity_document:
            return request.build_absolute_uri(obj.identity_document.url) if request else obj.identity_document.url
        return None


class RoomShareFinalReviewSerializer(serializers.ModelSerializer):
    room_title = serializers.SerializerMethodField()
    room_photo = serializers.SerializerMethodField()
    joining_members = serializers.SerializerMethodField()
    your_share_monthly_display = serializers.SerializerMethodField()
    group_security_deposit_display = serializers.SerializerMethodField()
    total_move_in_display = serializers.SerializerMethodField()

    class Meta:
        model = RoomShareRequest
        fields = [
            "id",
            "room_title",
            "room_photo",
            "joining_members",
            "your_share_monthly",
            "group_security_deposit",
            "total_move_in",
            "your_share_monthly_display",
            "group_security_deposit_display",
            "total_move_in_display",
            "status",
        ]

    def get_room_title(self, obj):
        return obj.room.apartment_title

    def get_room_photo(self, obj):
        request = self.context.get("request")
        first_photo = obj.room.photos.order_by("created_at").first()
        if first_photo and first_photo.image:
            return request.build_absolute_uri(first_photo.image.url) if request else first_photo.image.url
        return None

    def get_joining_members(self, obj):
        matches = MatchResult.objects.filter(user=obj.requester).order_by("-compatibility_score")[:2]
        request = self.context.get("request")
        data = []

        for match in matches:
            user = match.matched_user
            profile = UserProfile.objects.filter(user=user).first()

            photo = None
            if profile and getattr(profile, "profile_photo", None):
                photo = request.build_absolute_uri(profile.profile_photo.url) if request else profile.profile_photo.url
            elif profile and getattr(profile, "photo", None):
                photo = request.build_absolute_uri(profile.photo.url) if request else profile.photo.url

            data.append({
                "email": user.email,
                "full_name": profile.full_name if profile and profile.full_name else user.email,
                "photo": photo,
            })
        return data

    def get_your_share_monthly_display(self, obj):
        return f"${obj.your_share_monthly:,.2f}" if obj.your_share_monthly is not None else None

    def get_group_security_deposit_display(self, obj):
        return f"${obj.group_security_deposit:,.2f}" if obj.group_security_deposit is not None else None

    def get_total_move_in_display(self, obj):
        return f"${obj.total_move_in:,.2f}" if obj.total_move_in is not None else None


class RoomShareRequestSentSerializer(serializers.ModelSerializer):
    room_title = serializers.SerializerMethodField()

    class Meta:
        model = RoomShareRequest
        fields = [
            "id",
            "room_title",
            "status",
            "identity_verified",
            "created_at",
        ]

    def get_room_title(self, obj):
        return obj.room.apartment_title


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"


class BookingHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingHistory
        fields = "__all__"


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = "__all__"


class UserProfileImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "user",
            "photo",
            "profile_photo",
        ]