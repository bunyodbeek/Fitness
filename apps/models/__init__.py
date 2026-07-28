# apps/models/__init__.py

from apps.models.exercises import Exercise, ExerciseInstruction
from apps.models.users import (
	User,
	UserProfile,  # Added
	UserMotivation,  # Added
	UserProgram,
	WorkoutDay,  # Added
	UserProgramExercise  # Added
)
from apps.models.workouts import (
	Plan,
	Week,
	Workout,
	WorkoutExercise,
	Program,
	DayTemplate,
	DayTemplateExercise,
)
from apps.models.handbook import (
	HandbookCategory,
	HandbookSubCategory,
	HandbookItem,
)
from apps.models.support import SupportMessage
from apps.models.payments import (
	Payment,
	PremiumGift,
	Subscription,
	SubscriptionPlan,
)
from apps.models.favorites import (
	Favorite,
	FavoriteCollection,
	FavoriteExercise,
	FavoriteProgram,
	UserCustomProgram,
	CustomProgramProgress,
)
# DIQQAT: `apps.models.analytics` ATAYLAB import qilinmagan. `UserActivity`
# modeli hech qachon migratsiya qilinmagan (chunki u ham ro'yxatdan o'tmagan
# edi) va uni shu yerga qo'shish production'da yangi, ishlatilmaydigan jadval
# yaratardi. Uni jonlantirish alohida ish.

# DIQQAT: bu import'lar shunchaki qulaylik uchun emas. Django ilova yuklanganda
# faqat `apps.models` paketining O'ZINI (ya'ni shu fayl) import qiladi — shu
# yerda ko'rsatilmagan submodul modellari ro'yxatdan o'tmaydi. Loyihada Django
# admin o'chirilgan, shuning uchun ularni yuklaydigan boshqa hech narsa yo'q edi:
# `Subscription` faqat biror view import qilganda paydo bo'lardi. Natijada
# `UserProfile.subscription` teskari bog'lanishi bir muddat MAVJUD BO'LMAY turardi
# va `is_premium` noto'g'ri False qaytarishi mumkin edi — paywall middleware'i
# uchun bu pul to'lagan foydalanuvchini ilovadan qulflab qo'yish demakdir.
