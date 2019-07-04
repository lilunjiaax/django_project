from django.shortcuts import render

# Create your views here.
from django.views.generic import View

from django.http import JsonResponse

from goods.models import GoodsSKU

from django_redis import get_redis_connection

# 导入登录验证
from utils.mixin import LoginRequiredMixin

# 请求方式：ajax请求，视图函数返回的应答数据为JSON数据格式


# get传参数：/cart/add?sku_id=1&count=3
# post传参：['sku_id' : 1 , 'count' : 3]
# url传参：url配置时捕获参数


# Ajax发起的请求都在后台，浏览器看不到效果，不能使用mixin,就算返回登录页面，我们也无法看到显示的页面
# /cart/add
class CartAddView(View):
	'''购物车记录添加'''
	def post(self, request):
		user = request.user
		if not user.is_authenticated():
			# 用户未登录
			return JsonResponse({'res':0,'errmsg':'请先登录'})
		'''添加购物车记录'''
		# 1.接收数据
		sku_id = request.POST.get('sku_id')
		count = request.POST.get('count')


		# 2.数据校验
		if not all([sku_id, count]):
			return JsonResponse({'res':1, 'errmsg':'数据不完整'})
		# 2.1检验添加的商品的数量
		try:
			count = int(count)
		except Exception as e:
			return JsonResponse(['res':2,'errmsg':'商品数据出错'])
		# 2.2验证商品是否存在
		try:
			sku = GoodsSKU.objects.get(id = sku_id)
		except GoodsSKU.DoesNotExist:
			# 商品不存在
			return JsonResponse(['res':3, 'errmsg':'商品不存在'])

		# 3.业务处理:添加购物车记录
		conn = get_redis_connection('default')
		cart_key = 'cart_%d'%user.id
		# 在redis中的存储形式为：cart_id:{'sku_id1':2,'sku_id2':3}
		# 先尝试取sku_id看看购物车中有没有该商品(不存在则返回None)
		cart_count = conn.hget(cart_key, sku_id)
		if cart_count:
			# 累加数目
			count += int(cart_count)

		# 检验商品的库存
		if count > sku.stock:
			return JsonResponse({'res':4,'errmsg':'商品库存不足'})
		# 设置hash中sku_id对应的值
		conn.hset(cart_key, sku_id, count)

		# 计算购物车中商品条目数
		total_count = conn.hlen(cart_key)
		# 4.返回应答
		return JsonResponse({'res':5, 'total_count':total_count, 'message':'添加成功'})

# /cart 
# 需要先登录，才可以访问购物车页面
class CartInfoView(LoginRequiredMixin, View):
	'''购物车页面显示'''
	def get(self, request):
		'''显示'''
		# 获取登录的用户
		user = request.user

		# 获取用户购物车中商品的信息
		conn = get_redis_connection('default')
		cart_key = 'cart_%d'%user.id
		# cart_id:{'sku_id1':2}
		caer_dict = conn.hgetall(cart_key)  #返回的是字典形式

		skus = []
		total_count = 0
		total_price = 0
		for sku_id, count in caer_dict.items():
			sku = GoodsSKU.objects.get(id = sku_id)
			# 计算商品的小计
			amount = sku.price*int(count)
			# 动态给sku增加属性(小计，数量)
			sku.amount = amount 
			sku.count = count
			skus.append(sku)
			total_count += int(count)
			total_price += amount

		# 组织上下文：
		context = {
			'total_count':total_count,
			'total_price':total_price,
			'skus':skus
		}

		return render(request, 'cart.html', context)


# 更新购物车记录
# 前端采用Ajax，POST请求
# 前端需要传递的参数为：sku_id,count
# /cart/update
class CartUpdateView(View):
	'''购物车记录更新'''
	def post(self, request):
		'''购物车记录更新'''
		user = request.user
		if not user.is_authenticated():
			# 用户未登录
			return JsonResponse({'res':0,'errmsg':'请先登录'})

		# 接收数据
		sku_id = request.POST.get('sku_id')
		count = request.POST.get('count')


		# 2.数据校验
		if not all([sku_id, count]):
			return JsonResponse({'res':1, 'errmsg':'数据不完整'})
		# 2.1检验添加的商品的数量
		try:
			count = int(count)
		except Exception as e:
			return JsonResponse(['res':2,'errmsg':'商品数据出错'])
		# 2.2验证商品是否存在
		try:
			sku = GoodsSKU.objects.get(id = sku_id)
		except GoodsSKU.DoesNotExist:
			# 商品不存在
			return JsonResponse(['res':3, 'errmsg':'商品不存在'])


		# 业务处理：更新购物车记录
		conn = get_redis_connection('default')
		cart_key = 'cart_%d'%user.id

		# 检验商品的库存
		if count > sku.stock:
			return JsonResponse({'res':4,'errmsg':'商品库存不足'})
		
		# 更新
		conn.hset(cart_key, sku_id, count)

		# 计算用户购物车中的总件数
		total_count = 0
		vals = conn.hvals(cart_key)
		for val in vals:
			total_count += int(val)

		# 返回应答
		return JsonResponse({'res':5,'total_count':total_count,'message':'更新成功'})


# 删除购物车记录
# 采用Ajax post请求
# 前端需要传递的参数为：sku_id
# /cart/delete

class CartDeleteView(View):
	'''删除购物车记录'''
	def post(self, request):
		'''删除'''
		user = request.user
		if not user.is_authenticated():
			# 用户未登录
			return JsonResponse({'res':0,'errmsg':'请先登录'})

		# 接受参数
		sku_id = request.POST.get('sku_id')

		# 数据校验
		if not sku_id:
			return JsonResponse({'res':1,'errmsg':'无效的商品id'})

		# 检验商品是否存在
		try:
			sku = GoodsSKU.objects.get(id=sku_id)
		except GoodsSKU.DoesNotExist:
			# 商品不存在
			return JsonResponse({'res':2,'errmsg':'商品不存在'})

		# 业务处理
		conn = get_redis_connection('default')
		cart_key = 'cart_%d'%user.id

		# 删除
		conn.hdel(cart_key, sku_id)
		# 计算用户购物车中的总件数
		total_count = 0
		vals = conn.hvals(cart_key)
		for val in vals:
			total_count += int(val)
		# 返回应答
		return JsonResponse({'res':3,'total_count':total_count,'message':'成功'})


















