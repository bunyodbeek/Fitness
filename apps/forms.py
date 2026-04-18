from django import forms
from django.utils.translation import gettext_lazy as _
from root import settings

from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['name', 'gender', 'birth_date', 'weight', 'height', 'avatar', 'unit_system']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'input-field'}),
            'name': forms.TextInput(attrs={'class': 'input-field'}),
            'gender': forms.Select(attrs={'class': 'input-field'}),
            'weight': forms.NumberInput(attrs={'class': 'input-field'}),
            'height': forms.NumberInput(attrs={'class': 'input-field'}),
            'unit_system': forms.Select(attrs={'class': 'input-field'}),
            'avatar': forms.FileInput(attrs={'class': 'input-field'}),
        }

    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight is not None and weight <= 0:
            raise forms.ValidationError("Weight must be greater than zero.")
        return weight

    def clean_height(self):
        height = self.cleaned_data.get('height')
        if height is not None and height <= 0:
            raise forms.ValidationError("Height must be greater than zero.")
        return height


class LanguageSelectionForm(forms.Form):

    LANGUAGE_CHOICES = settings.LANGUAGES

    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=forms.RadioSelect,
        label=_("Select language")
    )
