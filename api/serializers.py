from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from .models import (
    UserLifestyle,
    UserBudgetLocation,
    MatchResult,
    UserProfile,
    UserAccountSettings,
    AppNotification,
    ListedRoom,
    ListedRoomPhoto,
    FavoriteMatch,
)

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(required=True)
    middle_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(required=True)
    age = serializers.IntegerField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "age",
            "address",
            "email",
            "phone_number",
            "password",
        ]

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name"),
            middle_name=validated_data.get("middle_name"),
            last_name=validated_data.get("last_name"),
            age=validated_data.get("age"),
            address=validated_data.get("address"),
            phone_number=validated_data.get("phone_number"),
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
            "age",
            "room_status",
            "photo",
            "about_me",
            "occupation",
            "target_area",
            "budget_range",
            "move_in_date",
        ]


class UserProfileDataSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "full_name",
            "age",
            "room_status",
            "photo",
            "about_me",
            "occupation",
            "target_area",
            "budget_range",
            "move_in_date",
        ]

    def get_photo(self, obj):
        request = self.context.get("request")
        if obj.photo:
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None


class UserProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    address = serializers.CharField(read_only=True)
    phone_number = serializers.CharField(read_only=True)
    profile = serializers.SerializerMethodField()
    lifestyle = serializers.SerializerMethodField()
    budget_location = serializers.SerializerMethodField()

    def get_profile(self, obj):
        try:
            profile = UserProfile.objects.get(user=obj)
            return UserProfileDataSerializer(profile, context=self.context).data
        except UserProfile.DoesNotExist:
            return None

    def get_lifestyle(self, obj):
        try:
            lifestyle = UserLifestyle.objects.get(user=obj)
            return UserLifestyleSerializer(lifestyle).data
        except UserLifestyle.DoesNotExist:
            return None

    def get_budget_location(self, obj):
        try:
            budget = UserBudgetLocation.objects.get(user=obj)
            return UserBudgetLocationSerializer(budget).data
        except UserBudgetLocation.DoesNotExist:
            return None


class MatchResultSerializer(serializers.ModelSerializer):
    matched_user = UserProfileSerializer(read_only=True)

    class Meta:
        model = MatchResult
        fields = "__all__"


class UserAccountSettingsSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = UserAccountSettings
        fields = ["email", "notifications_enabled", "language", "privacy_settings"]


class AppNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppNotification
        fields = "__all__"


class ListedRoomPhotoSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ListedRoomPhoto
        fields = ["id", "image"]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ListedRoomSerializer(serializers.ModelSerializer):
    photos = ListedRoomPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = ListedRoom
        fields = [
            "id",
            "apartment_title",
            "monthly_rent",
            "description",
            "is_active",
            "created_at",
            "updated_at",
            "photos",
        ]


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
        if profile and profile.full_name:
            return profile.full_name

        full_name = " ".join(
            filter(
                None,
                [
                    getattr(obj, "first_name", ""),
                    getattr(obj, "middle_name", ""),
                    getattr(obj, "last_name", ""),
                ],
            )
        ).strip()
        return full_name if full_name else obj.email

    def get_age(self, obj):
        profile = UserProfile.objects.filter(user=obj).first()
        if profile and profile.age is not None:
            return profile.age
        return getattr(obj, "age", None)

    def get_city(self, obj):
        budget = UserBudgetLocation.objects.filter(user=obj).first()
        if budget:
            return budget.preferred_city
        return getattr(obj, "address", None)

    def get_photo(self, obj):
        request = self.context.get("request")
        profile = UserProfile.objects.filter(user=obj).first()
        if profile and profile.photo:
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
        return profile.room_status if profile else None

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
    is_favorite = serializers.SerializerMethodField()
    first_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    address = serializers.CharField(read_only=True)
    phone_number = serializers.CharField(read_only=True)

    def _get_profile(self, obj):
        return UserProfile.objects.filter(user=obj).first()

    def _get_budget(self, obj):
        return UserBudgetLocation.objects.filter(user=obj).first()

    def _get_lifestyle(self, obj):
        return UserLifestyle.objects.filter(user=obj).first()

    def get_full_name(self, obj):
        profile = self._get_profile(obj)
        if profile and profile.full_name:
            return profile.full_name

        full_name = " ".join(
            filter(
                None,
                [
                    getattr(obj, "first_name", ""),
                    getattr(obj, "middle_name", ""),
                    getattr(obj, "last_name", ""),
                ],
            )
        ).strip()
        return full_name if full_name else obj.email

    def get_age(self, obj):
        profile = self._get_profile(obj)
        if profile and profile.age is not None:
            return profile.age
        return getattr(obj, "age", None)

    def get_city(self, obj):
        budget = self._get_budget(obj)
        if budget:
            return budget.preferred_city
        return getattr(obj, "address", None)

    def get_photo(self, obj):
        request = self.context.get("request")
        profile = self._get_profile(obj)
        if profile and profile.photo:
            return request.build_absolute_uri(profile.photo.url) if request else profile.photo.url
        return None

    def get_room_status(self, obj):
        profile = self._get_profile(obj)
        return profile.room_status if profile else None

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

    def get_is_favorite(self, obj):
        current_user = self.context.get("current_user")
        if not current_user:
            return False
        return FavoriteMatch.objects.filter(user=current_user, matched_user=obj).exists()