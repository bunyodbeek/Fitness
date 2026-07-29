import math
from datetime import date, timedelta

from django.contrib.auth.models import AbstractUser
from django.db.models import (
	CASCADE,
	BigIntegerField,
	BooleanField,
	CharField,
	DateField,
	DecimalField,
	ForeignKey,
	ImageField,
	IntegerField,
	OneToOneField,
	TextChoices, TextField, PositiveIntegerField, Model, DateTimeField,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.models.base import CreatedBaseModel
from apps.models.managers import UserManager

# Ro'yxatdan o'tgandan keyin ilova to'liq ochiq turadigan kunlar soni. Shu muddat
# tugagach obunasi yo'q foydalanuvchi premium sahifasida qamalib qoladi
# (apps/middleware.py: PaywallGateMiddleware).
TRIAL_DAYS = 7


class User(AbstractUser):
	class RoleType(TextChoices):
		ADMIN = 'admin', 'Admin'
		MODERATOR = 'moderator', 'Moderator'
		USER = 'user', 'User'
	
	role = CharField(max_length=20, choices=RoleType.choices, default=RoleType.USER)
	
	objects = UserManager()


class UserProfile(CreatedBaseModel):
	class Gender(TextChoices):
		MALE = 'male', _('Male')
		FEMALE = 'female', _('Female')
	
	class UnitSystem(TextChoices):
		METRIC = 'metric', _('Metric')
		ENGLISH = 'english', _('English')
	
	class ExperienceLevel(TextChoices):
		BEGINNER = 'beginner', _('Beginner')
		ADVANCED = 'advanced', _('Advanced')
	
	class FitnessGoal(TextChoices):
		BUILD_BODY = 'build_body', _('Build a great body')
		LOSE_WEIGHT = 'lose_weight', _('Lose weight')
		GAIN_MUSCLE = 'gain_muscle', _('Gain muscle')
		GET_SHAPE = 'get_shape', _('Get in shape')

	class Language(TextChoices):
		UZ = 'uz', "O‘zbekcha"
		RU = 'ru', "Русский"
		EN = 'en', "English"

	user = OneToOneField('apps.User', CASCADE, related_name='profile')
	telegram_id = BigIntegerField(unique=True, null=True, blank=True)
	name = CharField(_('Name'), max_length=100, default='User')
	avatar = ImageField(_('Avatar'), upload_to='avatars/', blank=True, null=True)
	gender = CharField(_('Gender'), max_length=10, choices=Gender.choices, default=Gender.MALE)
	birth_date = DateField(_('Birth date'), null=True, blank=True)
	weight = DecimalField(_('Weight'), max_digits=5, decimal_places=1, null=True, blank=True)
	height = DecimalField(_('Height'), max_digits=5, decimal_places=1, null=True, blank=True)
	experience_level = CharField(_('Experience level'), max_length=20, choices=ExperienceLevel.choices, blank=True)
	fitness_goal = CharField(_('Fitness goal'), max_length=20, choices=FitnessGoal.choices, blank=True)
	workout_days_per_week = IntegerField(_('Workout days per week'), null=True, blank=True)
	unit_system = CharField(_('Unit system'), max_length=10, choices=UnitSystem.choices, default=UnitSystem.METRIC)
	onboarding_completed = BooleanField(_('Onboarding completed'), default=False)

	# Foydalanuvchi tanlagan til — BOT xabarlari uchun. Ilovaning o'zi tilni
	# cookie/sessiyadan oladi, lekin bot xabarlari cron'dan yoki webhook'dan
	# ketadi va u yerda so'rov konteksti umuman yo'q. Shuning uchun tanlov shu
	# yerda ham saqlanadi. Standart qiymat `uz`: bu maydon paydo bo'lgunga qadar
	# BARCHA bot xabarlari o'zbekcha edi, ya'ni eski foydalanuvchilar uchun hech
	# narsa o'zgarmaydi.
	language = CharField(
		_('Language'), max_length=5, choices=Language.choices, default=Language.UZ,
	)

	# Bepul sinov davri (7 kun) SHU paytdan boshlanadi. `created_at` emas, alohida
	# maydon — chunki `created_at` qator yaratilishining nojo'ya ta'siri, bu esa
	# to'lov qoidasi. Bir marta yoziladi va HECH QACHON o'zgarmaydi: qayta login,
	# Telegram initData qayta berilishi yoki anketani qayta to'ldirish uni
	# tiklamaydi (identifikatsiya `telegram_id` orqali, `User` qatori esa
	# `telegram_<id>` username bilan qayta yaratilmaydi). Eski foydalanuvchilar
	# uchun migratsiya buni deploy vaqtiga qo'yadi — hamma yangidan 7 kun oladi.
	trial_started_at = DateTimeField(_('Trial started at'), null=True, blank=True, editable=False)

	# Sinov tugashi haqida oxirgi yuborilgan eslatma (necha kun qolganda).
	# Cron kuniga bir marta ishlashi KAFOLATLANMAGAN — qayta ishga tushirish,
	# ikki marta rejalashtirish yoki qo'lda chaqirish bo'lishi mumkin. Bu maydon
	# bir xil eslatma ikki marta bormasligini ta'minlaydi: 3 → 2 → 1 tartibida
	# faqat KAMAYIB borgan qiymat yuboriladi.
	trial_reminder_sent_day = PositiveIntegerField(
		_('Last trial reminder (days left)'), null=True, blank=True, editable=False,
	)

	class Meta:
		verbose_name = _('User Profile')
		verbose_name_plural = _('User Profiles')

	def __str__(self):
		return f"{self.name}"

	def save(self, *args, **kwargs):
		# Anchor faqat BIRINCHI saqlashda yoziladi va keyin hech qachon
		# o'zgarmaydi.
		#
		# Ilgari bu yerda `user.date_joined` ishlatilardi — g'oya profil o'chib
		# qayta yaratilsa sinov qaytadan boshlanmasin edi. Lekin `User` qatori
		# profildan ANCHA oldin yaratilgan bo'lishi mumkin: `get_or_update_user`
		# uni `telegram_<id>` username bo'yicha `get_or_create` qiladi, ya'ni
		# anketani tugatmay tashlab ketgan odam qaytib kelganda `date_joined`
		# haftalar oldingi sana bo'ladi. Natijada sinov O'TMISHDA boshlanib,
		# ro'yxatdan o'tgan zahoti tugagan holda ko'rinardi.
		#
		# Sinov ro'yxatdan o'tish PAYTIDAN boshlanadi — profil aynan shunda
		# yaratiladi.
		if self.trial_started_at is None:
			self.trial_started_at = timezone.now()
			update_fields = kwargs.get('update_fields')
			if update_fields is not None:
				kwargs['update_fields'] = list(update_fields) + ['trial_started_at']
		super().save(*args, **kwargs)

	@property
	def is_premium(self) -> bool:
		subscription = getattr(self, "subscription", None)
		return bool(subscription and subscription.is_valid)

	@property
	def trial_ends_at(self):
		"""Bepul sinov qachon tugaydi. Anchor yo'q bo'lsa None."""
		if self.trial_started_at is None:
			return None
		return self.trial_started_at + timedelta(days=TRIAL_DAYS)

	@property
	def is_in_trial(self) -> bool:
		"""Hali bepul 7 kun ichidami."""
		ends = self.trial_ends_at
		return bool(ends and timezone.now() < ends)

	@property
	def trial_days_left(self) -> int:
		"""Sinovgacha qolgan to'liq kunlar, yuqoriga yaxlitlangan (0.5 kun → 1)."""
		ends = self.trial_ends_at
		if not ends:
			return 0
		seconds = (ends - timezone.now()).total_seconds()
		if seconds <= 0:
			return 0
		return math.ceil(seconds / 86400)

	@property
	def has_app_access(self) -> bool:
		"""Ilovadan foydalana oladimi — paywall gate'ning YAGONA manbasi.

		Premium (yoki sovg'a qilingan) obuna → doim ochiq. Aks holda faqat
		sinov muddati ichida. Obunasi tugaganlar sinovga QAYTMAYDI: ular uchun
		`is_in_trial` allaqachon False (anchor ro'yxatdan o'tish paytida qotgan),
		shuning uchun yangi va qaytgan mijoz uchun alohida qoida kerak emas."""
		return self.is_premium or self.is_in_trial

	@property
	def age(self):
		if self.birth_date:
			today = date.today()
			is_before_birthday = (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
			return today.year - self.birth_date.year - int(is_before_birthday)
		return None
	
	@property
	def bmi(self):
		if self.weight and self.height:
			height_m = float(self.height) / 100
			return round(float(self.weight) / (height_m ** 2), 1)
		return None


class UserMotivation(CreatedBaseModel):
	class MotivationType(TextChoices):
		HEALTHY_LIFESTYLE = 'healthy_lifestyle', _('I want a healthy lifestyle')
		IMPROVE_PHYSIQUE = 'improve_physique', _('Improve my physique')
		GET_STRONGER = 'get_stronger', _('Get stronger every day')
		GOOD_CHALLENGE = 'good_challenge', _('I like a good challenge')
	
	user = ForeignKey('apps.UserProfile', CASCADE, related_name='motivations')
	motivation = CharField(_('Motivation'), max_length=30, choices=MotivationType.choices)
	
	class Meta:
		unique_together = ['user', 'motivation']
		verbose_name = _('User Motivation')
		verbose_name_plural = _('User Motivations')
	
	def __str__(self):
		return f"{self.user.name} - {self.get_motivation_display()}"


class UserProgram(CreatedBaseModel):
	user = ForeignKey('apps.UserProfile', CASCADE, related_name='program_assignments')
	program = ForeignKey('apps.Program', CASCADE, related_name='user_assignments')
	is_active = BooleanField(_('Is active'), default=True)
	assigned_once = BooleanField(_('Assigned once'), default=False)
	
	class Meta:
		verbose_name = _('User Program')
		verbose_name_plural = _('User Programs')
	
	def __str__(self):
		return f"{self.user.name} - {self.program.name}"


class WorkoutDay(Model):
	class CompleteStatus(TextChoices):
		NOT_STARTED = 'not_started', _('Not started')
		UNFINISHED = 'unfinished', _('Unfinished')
		COMPLETED = 'completed', _('Completed')
	
	program = ForeignKey('apps.UserProgram', CASCADE, related_name='workout_days')
	status = CharField(_('Status'), max_length=20, choices=CompleteStatus.choices, default=CompleteStatus.NOT_STARTED)
	order = PositiveIntegerField(_('Order'))
	title = CharField(_('Title'), max_length=100)
	body_part = CharField(_('Body part'), max_length=100)
	completed_at = DateTimeField(_('Completed at'), auto_now_add=True)
	
	class Meta:
		ordering = ['order']
		unique_together = ('program', 'order')
	
	def __str__(self):
		return f"day - {self.order} - {self.program}"


class UserProgramExercise(Model):
	day = ForeignKey('apps.WorkoutDay', CASCADE, related_name='exercises')
	exercise = ForeignKey('apps.Exercise', CASCADE)
	sets = PositiveIntegerField(_('Sets'))
	reps = PositiveIntegerField(_('Reps'))
