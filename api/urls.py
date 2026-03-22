from django.urls import path
from .views import (
    SendOTPView,
    VerifyOTPView,
    RegisterView,
    LoginView,
    ForgotPasswordView,
    ResetPasswordView,
    UserLifestyleView,
    UserBudgetLocationView,
    UserProfileCreateUpdateView,
    UserProfileView,
    MatchListView,
    MatchDetailView,
    SaveFavoriteMatchView,
    FavoriteListView,
    ViewGroupDetailView,
    StartGroupChatView,
    GroupChatDetailView,
    GroupChatSendMessageView,
    GroupChatShareRoomDetailsView,
    GroupChatToggleMuteView,
    GroupChatUploadImageView,
    GroupChatEmojiListView,
    ScheduleRoomTourView,
    RoomTourDetailView,
    ConfirmRoomBookingView,
    RoomBookingDetailView,
    DirectChatCreateOrGetView,
    DirectChatDetailView,
    DirectChatSendMessageView,
    MessagesInboxView,
    ProfileDashboardView,
    ProfileUpdateView,
    ProfilePhotoUploadView,
    AccountSettingsView,
    ChangeEmailView,
    ChangePasswordView,
    DeleteAccountView,
    NotificationsListView,
    MarkNotificationReadView,
    ListedRoomCreateUpdateView,
    ListedRoomDetailView,
    HomeRoomsListView,
    HomeRoomDetailView,
    RoomShareRequestFormView,
    SubmitRoomShareRequestView,
    RoomShareRequestDetailView,
    RoomShareVerificationView,
    UploadIdentityDocumentView,
    RoomShareFinalReviewView,
    SendRoomShareRequestView,
    RoomShareRequestSentView,
    LogoutView,
    DiscoverRoommatesView,
    RoommateProfileDetailView,
    AICompatibilityView,
)

urlpatterns = [

    # ================= AUTH =================
    path("send-otp/", SendOTPView.as_view()),
    path("verify-otp/", VerifyOTPView.as_view()),
    path("register/", RegisterView.as_view()),
    path("login/", LoginView.as_view()),
    path("forgot-password/", ForgotPasswordView.as_view()),
    path("reset-password/", ResetPasswordView.as_view()),
    path("logout/", LogoutView.as_view()),

    # ================= ONBOARDING =================
    path("lifestyle/", UserLifestyleView.as_view()),
    path("budget-location/", UserBudgetLocationView.as_view()),

    # ================= PROFILE =================
    path("user-profile/", UserProfileCreateUpdateView.as_view()),
    path("profile/<str:email>/", UserProfileView.as_view()),
    path("profile-dashboard/<str:email>/", ProfileDashboardView.as_view()),
    path("profile-update/", ProfileUpdateView.as_view()),
    path("profile-photo-upload/", ProfilePhotoUploadView.as_view()),

    # ================= MATCHES =================
    path("matches/<str:email>/", MatchListView.as_view()),
    path("match-detail/<int:match_id>/", MatchDetailView.as_view()),
    path("save-favorite/", SaveFavoriteMatchView.as_view()),
    path("favorites/<str:email>/", FavoriteListView.as_view()),

    # ================= DISCOVER + AI =================
    path("discover-roommates/<str:email>/", DiscoverRoommatesView.as_view()),
    path("roommate-profile/<str:current_email>/<str:target_email>/", RoommateProfileDetailView.as_view()),
    path("ai-compatibility/<str:current_email>/<str:target_email>/", AICompatibilityView.as_view()),

    # ================= GROUP =================
    path("view-group/<str:email>/", ViewGroupDetailView.as_view()),
    path("start-group-chat/", StartGroupChatView.as_view()),
    path("group-chat/<int:chat_id>/", GroupChatDetailView.as_view()),
    path("group-chat/send-message/", GroupChatSendMessageView.as_view()),
    path("group-chat/share-room-details/", GroupChatShareRoomDetailsView.as_view()),
    path("group-chat/toggle-mute/", GroupChatToggleMuteView.as_view()),
    path("group-chat/upload-image/", GroupChatUploadImageView.as_view()),
    path("group-chat/emojis/", GroupChatEmojiListView.as_view()),

    # ================= DIRECT CHAT =================
    path("direct-chat/create/", DirectChatCreateOrGetView.as_view()),
    path("direct-chat/<int:chat_id>/<str:email>/", DirectChatDetailView.as_view()),
    path("direct-chat/send-message/", DirectChatSendMessageView.as_view()),
    path("messages/<str:email>/", MessagesInboxView.as_view()),

    # ================= ROOMS =================
    path("listed-room/", ListedRoomCreateUpdateView.as_view()),
    path("listed-room/<str:email>/", ListedRoomDetailView.as_view()),
    path("home-rooms/<str:email>/", HomeRoomsListView.as_view()),
    path("home-room-detail/<int:room_id>/<str:email>/", HomeRoomDetailView.as_view()),

    # ================= ROOM SHARE =================
    path("room-share-form/<int:room_id>/<str:email>/", RoomShareRequestFormView.as_view()),
    path("submit-room-share-request/", SubmitRoomShareRequestView.as_view()),
    path("room-share-request/<int:request_id>/", RoomShareRequestDetailView.as_view()),
    path("room-share-verification/<int:request_id>/", RoomShareVerificationView.as_view()),
    path("upload-identity-document/", UploadIdentityDocumentView.as_view()),
    path("room-share-final-review/<int:request_id>/", RoomShareFinalReviewView.as_view()),
    path("send-room-share-request/", SendRoomShareRequestView.as_view()),
    path("room-share-request-sent/<int:request_id>/", RoomShareRequestSentView.as_view()),

    # ================= TOUR & BOOKING =================
    path("schedule-room-tour/", ScheduleRoomTourView.as_view()),
    path("room-tour/<int:schedule_id>/", RoomTourDetailView.as_view()),
    path("confirm-room-booking/", ConfirmRoomBookingView.as_view()),
    path("room-booking/<int:booking_id>/", RoomBookingDetailView.as_view()),

    # ================= SETTINGS =================
    path("account-settings/<str:email>/", AccountSettingsView.as_view()),
    path("account-settings/", AccountSettingsView.as_view()),
    path("change-email/", ChangeEmailView.as_view()),
    path("change-password/", ChangePasswordView.as_view()),
    path("delete-account/", DeleteAccountView.as_view()),

    # ================= NOTIFICATIONS =================
   path("notifications/mark-read/", MarkNotificationReadView.as_view(), name="notifications-mark-read"),
   path("notifications/<str:email>/", NotificationsListView.as_view(), name="notifications-list"),
]