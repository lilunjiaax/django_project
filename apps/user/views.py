from django.shortcuts import render,redirect
import re

from django.http import HttpResponse

# 导入反向解析的函数
from django.core.urlresolvers import reverse

# 导入类视图所需要　继承的类
from django.views.generic import View

from user.models import User,Address

from goods.models import GoodsSKU

from goods.models import OrderInfo,OrderGoods

from django.core.paginator import Paginator

# 导入加密的第三方库
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
# 导入加密时过期报出的异常
from itsdangerous import SignatureExpired
# 导入　settings 为了使用里面的　加密密钥
from django.conf import settings

# 导入发送邮件的函数
from django.core.mail import send_mail

# 导入中间人函数
from celery_tasks.tasks import send_register_active_email

# 导入django 自带的用户认证函数,退出用户函数
from django.contrib.auth import authenticate,login,logout

# 导入登录验证类（从公共文件夹）
from utils.mixin import LoginRequiredMixin

# 导入关于redis数据库读写的函数
from django_redis import get_redis_connection

# /user/register
def register(request):
	
	if request.method == 'GET':
		'''显示注册页面'''
		return render(request, 'register.html')
	else:
		username = request.POST.get('user_name')
		password = request.POST.get('pwd')
		email = request.POST.get('email')
		allow = request.POST.get('allow')

		# ２．数据校验
		if not all([username,password,email]):
			return render(request, 'register.html', {'errmsg':'数据不完整'})
	
		# 校验邮箱
		if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
			return render(request, 'register.html', {'errmsg':'邮箱格式不合法'})

		# 校验是否同意协议
		if allow != 'on':
			return render(request, 'register', {'errmsg':'请同意协议'})

		# 校验用户名是否重复
		try:
			user = User.objects.get(username = username)
		except User.DoesNotExist:
			# 用户名不存在，可以注册
			user = None
		if user:
			return render(request, 'register.html', {'errmsg':'用户名已经存在'})
		# ３．进行业务处理：进行用户注册
		user = User.objects.create_user(username, email, password)
		# 设置该用户默认是不激活的
		user.is_active = 0
		user.save()

		# ４．返回应答,跳转到首页
		return redirect(reverse('goods:index'))


def register_handle(request):
	'''注册处理视图函数'''
	# 1.接受数据
	username = request.POST.get('user_name')
	password = request.POST.get('pwd')
	email = request.POST.get('email')
	allow = request.POST.get('allow')

	# ２．数据校验
	if not all([username,password,email]):
		return render(request, 'register.html', {'errmsg':'数据不完整'})
	
	# 校验邮箱
	if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
		return render(request, 'register.html', {'errmsg':'邮箱格式不合法'})

	# 校验是否同意协议
	if allow != 'on':
		return render(request, 'register', {'errmsg':'请同意协议'})

	# 校验用户名是否重复
	try:
		user = User.objects.get(username = username)
	except User.DoesNotExist:
		# 用户名不存在，可以注册
		user = None
	if user:
		return render(request, 'register.html', {'errmsg':'用户名已经存在'})
	# ３．进行业务处理：进行用户注册
	user = User.objects.create_user(username, email, password)
	# 设置该用户默认是不激活的
	user.is_active = 0
	user.save()
	# ４．返回应答,跳转到首页
	return redirect(reverse('goods:index'))


# 类视图
class Register(View):
	'''注册'''
	def get(self, request):
		return render(request, 'register.html')
	def post(self, request):
		# 1.接受数据
		username = request.POST.get('user_name')
		password = request.POST.get('pwd')
		email = request.POST.get('email')
		allow = request.POST.get('allow')

		# ２．数据校验
		if not all([username,password,email]):
			return render(request, 'register.html', {'errmsg':'数据不完整'})
	
		# 校验邮箱
		if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
			return render(request, 'register.html', {'errmsg':'邮箱格式不合法'})

		# 校验是否同意协议
		if allow != 'on':
			return render(request, 'register', {'errmsg':'请同意协议'})

		# 校验用户名是否重复
		try:
			user = User.objects.get(username = username)
		except User.DoesNotExist:
			# 用户名不存在，可以注册
			user = None
		if user:
			return render(request, 'register.html', {'errmsg':'用户名已经存在'})
		# ３．进行业务处理：进行用户注册
		user = User.objects.create_user(username, email, password)
		# 设置该用户默认是不激活的
		user.is_active = 0
		user.save()

		# 发送激活邮件，包含激活链接　http://127.0.0.1:8000/user/active/ id(数据表中的id)
		# 激活链接中需要包含用户的身份信息，并且把身份信息进行加密

		# 加密用户信息，生成激活token
		serializer = Serializer(settings.SECRET_KEY, 3600)
		info = {'confirm':user.id}
		# 加密得到的密文以　字节流　形似
		token = serializer.dumps(info)
		# 需要解码成　字符串　形式
		token = token.decode('utf8')

		# 发邮件　delay()放入任务队列
		send_register_active_email.delay(email, username, token)
		# subject = '天天生鲜欢迎信息'
		# message = ''
		# # 当发送信息中有标签时，使用html_message方式传输
		# html_message = '''<h1>%s, 欢迎</h1>点击链接，激活账户.<br><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>'''%(username,token,token)
		# sender = settings.EMAIL_FROM
		# receiver = [email]
		# send_mail(subject, message, sender, receiver,html_message = html_message)
		
		# ４．返回应答,跳转到首页
		return redirect(reverse('goods:index'))


class ActiveView(View):
	'''用户激活'''
	def get(self,request, token):
		# 解密，获取需要激活的信息
		serializer = Serializer(settings.SECRET_KEY, 3600)
		try:
			info = serializer.loads(token)

			user_id = info['confirm']

			user = User.objects.get(id = user_id)
			user.is_active = 1
			user.save()
			return redirect(reverse('user:login'))
		except SignatureExpired as e:
			return HttpResponse('激活信息过期')



# /user/login
class LoginView(View):
	'''登录'''
	def get(self, request):
		'''显示登录页面'''
		# 需要验证是否有cookie信息需要填写
		if 'username' in request.COOKIES:
			username = request.COOKIES.get('username')
			checked = 'checked'
		else:
			username = ''
			checked = ''
		return render(request, 'login.html', {'username':username, 'checked':checked})


	def post(self, request):
		'''登录校验'''
		# 获取表单提交的数据
		username = request.POST.get('username')
		password = request.POST.get('pwd')

		# 验证数据的完整性
		if not all([username, password]):
			return render(request, 'login.html', {'errmsg':'数据不完整'})

		# 使用django模块自带的用户认证模块
		# 验证成功，返回User对象，　认证失败，返回None
		user = authenticate(username = username, password = password)

		if user is not None:
			# 账号密码验证通过
			if user.is_active:

				# 获取登陆后后需要跳转的地址,并设置返回默认值
				next_url = request.GET.get('next', reverse('goods:index'))
				response = redirect(next_url)
				# 判断用户是否需要记住用户名
				# remember 勾选是on ,没有勾选是 None
				remember = request.POST.get('remember')
				if remember == 'on':
					response.set_cookie('username',username, max_age = 7*24*2600)
				else:
					response.delete_cookie('username')
				# 用户已经激活，要记录用户的登录状态
				login(request, user)
				# return redirect(reverse('goods:index'))
				
				return response


			else:
				print('not active , refuse')
		else:
			return render(request, 'login.html', {'message':'用户名或密码错误'})


# /user/logout
class LogoutView(View):
	'''退出登录'''
	def get(self, request):
		# 清楚用户的session信息
		logout(request)
		# 跳转到首页
		return redirect(reverse("goods:index"))

# /user
class UserInfoView(View):
	'''用户中心－信息页'''
	def get(self, request):
		#.page = 'user'
		# Django会给request对象添加一个属性request.user
		# 如果用户未登录，user是AnonymousUser类的一个实例
		# 如果用户登录，user是User的一个实例，直接可以使用它的一些属性。

		# request.user.is_authenticated()
		# 除了你给模板文件传递的模板变量之外，django框架会将
		# request.user传给模板文件

		# 获取用户的个人信息
		user = request.user

		# 使用封装好的模型管理器类方法
		address = Address.objects.get_default_address(user)
		
		# 获取用户的浏览记录,使用redis数据库
		# from redis import StrictRedis
		# str = StrictRedis(host='127.0.0.1', port='6379', db=9)
		
		# 链接到redis数据库的链接
		con = get_redis_connection('default')

		# 拼接出对应历史浏览记录的key 
		# 因为redis数据库采取的是　key , value　结构存储
		history_key = 'history_%d'%user.id
		# 获取用户最新浏览的５个商品的id
		sku_ids = con.lrange(history_key, 0, 4)

		# 想要按照浏览顺序显示,必须要遍历查询，因为数据库查询会自动排序（打乱原本的顺序）
		goods_li = []
		for id in sku_ids:
			goods = GoodsSKU.objects.get(id = id)
			goods_li.append(goods)

		# 组织上下文
		context = {'page':'user', 'address':address, 'goods_li':goods_li}

		return render(request, 'user_center_info.html', context)


# /user/order
class UserOrderView(LoginRequiredMixin, View):
	'''用户中心－订单页'''
	def get(self, request, page):

		# 获取用户的订单信息
		user = request.user

		# 获取的orders是一个查询集，因为用户可能有很多订单。
		orders = OrderInfo.objects.filter(user = user).order_by('-create_time')
		for order in orders:
			# order_skus是一个和某个订单关联的所有商品的查询集
			order_skus = OrderGoods.objects.filter(order_id = order.order_id)
			for order_sku in order_skus:
				# 计算商品的小计
				amount = order_sku.count * order_sku.price

				# 动态给每件商品增加属性
				order_sku.amount = amount
			# 动态的给order增加属性，保存订单商品的信息
			order.order_skus = order_skus
			# 保存订单状态标题
			order.status_name = OrderInfo.ORDER_STATUS[order.order_status]


		# 需要去进行分页
		paginator = Paginator(orders, 1)

		# 处理页码
		try:
			page = int(page)
		except:
			page = 1
		if page > paginator.num_pages:
			page = 1
		# 获取第page页的实例对象
		order_page = paginator.page(page)

		# todo:进行页码控制，页面上最多显示５个页码
		
		# 1.总页数小于５页，全部显示
		# ２．如果当前页为前３页，显示１－５页
		# ３．如果当前页是后３页，显示后５页
		# ４．其他情况，显示当前页的前２页，当前页，当前页的后２页
		num_pages = paginator.num_pages
		if num_pages < 5:
			pages = range(1, num_pages+1)
		elif page <= 3:
			pages = range(1, 6)
		elif num_pages - page <= 2:
			pages = range(num_pages-4, num_pages+1)
		else:
			pages = range(page-2, page+3)

		# 组织上下文
		context = {'order_page':order_page,
					'pages':pages,
					'page':'order'}

		return render(request, 'user_center_order.html', context)


# /user/address
class AdressView(View):
	'''用户中心－地址页'''
	def get(self, request):

		# 获取用户的默认收货地址
		# 获取登录用户的user对象
		user = request.user

		# try:
		# 	address = Address.objects.get(user = user, is_default = True)
		# except Address.DoesNotExist:
		# 	# 不存在默认收货地址
		# 	address = None
		# 使用封装好的模型管理器类方法
		address = Address.objects.get_default_address(user)


		return render(request, 'user_center_site.html',{'page':'address','address':address})

	def post(self, request):
		'''地址的添加'''
		# 1.接受数据
		receiver = request.POST.get('receiver')
		addr = request.POST.get('addr')
		zip_code = request.POST.get('zip_code')
		phone = request.POST.get('phone')


		# 2.校验数据
		if not all([receiver, addr, phone]):
			return render(request, 'user_center_site.html', {'errmsg':'数据不完整'})
		# 校验手机号
		if not re.match(r'^1[3|4|5|7|8][0-9]{9}$',phone):
			return render(request, 'user_center_site.html', {'errmsg':'手机格式不正确'})


		# ３.业务处理，地址添加
		# 如果用户已存在默认收货地址，添加的地址不作为默认收货地址，否则作为默认收货地址

		# 获取登录用户的user对象
		user = request.user

		# try:
		# 	address = Address.objects.get(user = user, is_default = True)
		# except Address.DoesNotExist:
		# 	# 不存在默认收货地址
		# 	address = None

		# 使用封装好的模型管理器类方法
		address = Address.objects.get_default_address(user)

		if address:
			is_default = False
		else:
			is_default = True

		Address.objects.create(user = user, 
								receiver = receiver, 
								addr = addr,
								zip_code = zip_code,
								phone = phone,
								is_default = is_default)


		# 返回应答，刷新地址页面
		return redirect(reverse('user:address'))  # get请求方式




























