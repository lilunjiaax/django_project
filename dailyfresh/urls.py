from django.conf.urls import include,url
from django.contrib import admin
# urlpatterns = [
#     url(r'^admin/', include(admin.site.urls)),
#     url(r'^tinymce/',include('tinymce.urls')), # 富文本编辑器
    
#     url(r'^user/', include('user.urls', namespace = 'user')),
#     url(r'^order/',include('order.urls' namespace = 'order')),
#     url(r'^cart/',include('cart.urls', namespace = 'cart')),
#     url(r'^',include('goods.urls', namespace = 'goods')),
# ]

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^tinymce/', include('tinymce.urls')), # 富文本编辑器
    url(r'^user/', include('user.urls', namespace='user')), # 用户模块
    url(r'^cart/', include('cart.urls', namespace='cart')), # 购物车模块
    url(r'^search',include('haystack.urls')),#全文检索框架
    url(r'^order/', include('order.urls', namespace='order')), # 订单模块
    url(r'^', include('goods.urls', namespace='goods')), # 商品模块
]




