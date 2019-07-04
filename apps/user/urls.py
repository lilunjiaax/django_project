
from django.conf.urls import url
from user import views
from user.views import Register,ActiveView,LoginView,UserInfoView,UserOrderView,AdressView,LogoutView
# 导入django自带的登录装饰器
from django.contrib.auth.decorators import login_required

urlpatterns = [
	# url(r'^register$',views.register, name = 'register'),
	# url(r'^register_handle$',views.register_handle, name = 'register_handle'),
	url(r'^register$',Register.as_view(), name = 'register'),
	url(r'^active/(?P<token>.*)', ActiveView.as_view(), name = 'active'),

	url(r'^login$', LoginView.as_view(), name = 'login'),
	url(r'^logout$', LogoutView.as_view(), name = 'logout'),

	url(r'^order/(?P<page>\d+)$',UserOrderView.as_view(), name = 'order'),
	# url(r'^order$',login_required(UserOrderView.as_view()), name = 'order'),
	url(r'^adress$',login_required(AdressView.as_view()), name = 'adress'),
	url(r'^$',login_required(UserInfoView.as_view()), name = 'user'),
]
