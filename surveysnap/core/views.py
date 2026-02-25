from django.shortcuts import render,redirect
from .forms import UserSignupForm, UserLoginForm
from django.contrib.auth import authenticate,login

def homeView(request):
  return render(request,'core/home.html')

# Create your views here.
def userSignupView(request):
    if request.method =="POST":
      form = UserSignupForm(request.POST or None)
      if form.is_valid():
        form.save()
        return redirect('login') 
      else:
        return render(request,'core/signup.html',{'form':form})  
    else:
        form = UserSignupForm()
        return render(request,'core/signup.html',{'form':form})
    
def userLoginView(request):
  if request.method =="POST":
    form = UserLoginForm(request.POST or None)
    if form.is_valid():
      print(form.cleaned_data)
      email = form.cleaned_data['email']
      password = form.cleaned_data['password']
      user = authenticate(request,email=email,password=password) 
      if user:
        login(request,user)
        if user.role == "admin":
          return redirect("admin_dashboard") 
        elif user.role == "creator":
          return redirect("creator_dashboard") 
        elif user.role == "respondent":
          return redirect("respondent_dashboard") 
      else:
        return render(request,'core/login.html',{'form':form})  
    
  else:
    form = UserLoginForm()
    return render(request,'core/login.html',{'form':form})