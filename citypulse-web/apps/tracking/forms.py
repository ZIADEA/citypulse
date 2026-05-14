from django import forms


class DeliveryConfirmationForm(forms.Form):
    order_ref = forms.CharField(max_length=100)
    status = forms.CharField(max_length=32)
    eta = forms.DateTimeField(required=False)
    photo = forms.ImageField(required=False)
    signature = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
