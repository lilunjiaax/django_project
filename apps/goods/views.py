from django.shortcuts import render,redirect

from django.core.urlresolvers import reverse

from django.views.generic import View

# 导入设置缓存的函数
from django.core.cache import cache

from goods.models import GoodsSKU,GoodsType,IndexPromotionBanner,IndexGoodsBanner,IndexTypeGoodsBanner

# 导入商品的评论（在订单表里面）
from order.models import OrderGoods

# 导入django　的　redis库
from django_redis import get_redis_connection

# 导入对查询集的分页方法
from django.core.paginator import Paginator
# from django_redis import get_redis_connection


# Create your views here.


# http://127.0.0.1:8000
class IndexView(View):
	'''首页'''
	def get(self, request):
		'''显示首页'''
		# 尝试从缓存中获取数据
		context = cache.get('index_page_data')
		if context is None:
			print('设置缓存')
			# 缓存中没有数据
			# 获取商品的种类信息
			types = GoodsType.objects.all()

			# 获取首页轮播商品信息,查询的结果需要排展示顺序。
			goods_banners = IndexGoodsBanner.objects.all().order_by('index')

			# 获取首页促销活动信息,查询的结果需要排展示顺序。
			promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

			# 获取首页分类商品展示信息
			for type in types:
				# 获取type种类首页分类商品的图片展示信息
				image_banners = IndexTypeGoodsBanner.objects.filter(type = type, display_type = 1).order_by('index')
				# 获取type种类首页分类商品的文字展示信息
				title_banners = IndexTypeGoodsBanner.objects.filter(type = type, display_type = 0).order_by('index')

				# 动态的给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
				type.image_banners = image_banners
				type.title_banners = title_banners
	

			# 组织模板上下文
			context = {'types':types,
					   'goods_banners':goods_banners,
					   'promotion_banners':promotion_banners}

			# 设置缓存
			# (key,value,timeout)
			cache.set('index_page_data', context, 30)


		# 获取用户购物车中的商品的数目
		user = request.user
		cart_count = 0
		if user.is_authenticated():
			# 用户已经登录
			conn = get_redis_connection('default')
			cart_key = 'cart_%d'%user.id
			cart_count = conn.hlen(cart_key)

		# 组织模板上下文:字典相加
		context.update(cart_count = cart_count)

		# 使用模板
		# return render(request, 'static_index.html', context)
		return render(request, 'index.html', context)


# /goods/商品id
class DetailView(View):
	'''详情页'''
	def get(self, request, goods_id):
		'''显示详情页'''
		try:
			sku = GoodsSKU.objects.get(id = goods_id)
		except GoodsSKU.DoesNotExist:
			return redirect(reverse('goods:index'))
		
		# 获取商品的分类信息
		types = GoodsType.objects.all()

		# 获取商品的评论
		sku_orders = OrderGoods.objects.filter(sku = sku).exclude(comment = '')

		# 获取新品推荐信息(一定是同种类的新品)
		new_skus = GoodsSKU.objects.filter(type = sku.type).order_by('-create_time')[:2]   #减号　是作为降序排列

		# 获取同一个SPU的其他SKU
		same_spu_skus = GoodsSKU.objects.filter(goods = sku.goods).exclude(id = goods_id)


		# 获取用户购物车中的商品的数目
		user = request.user
		cart_count = 0
		if user.is_authenticated():
			# 用户已经登录
			conn = get_redis_connection('default')
			cart_key = 'cart_%d'%user.id
			cart_count = conn.hlen(cart_key)

			# 用户历史浏览记录的添加
			# 当用户访问详情页时，需要添加历史浏览记录
			conn = get_redis_connection('default')
			history_key = 'history_%d'%user.id
			# 移除该商品已经存在的历史记录
			conn.lrem(history_key, 0, goods_id)
			# 把goods_id在列表的最左侧插入
			conn.lpush(history_key, goods_id)

			# 只保存用户最先浏览的５条历史记录
			conn.ltrim(history_key, 0, 4)


		# 组织模板上下文
		context = {'sku':sku,
					'types':types,
					'sku_orders':sku_orders,
					'new_skus':new_skus,
					'same_spu_skus':same_spu_skus,
					'cart_count':cart_count}

		# 使用模板
		return render(request, 'detail.html',context)



# 点击首页的总类时会跳转到列表页

# 种类id,页码，排序标准（默认，人气，价格）

# /list/种类id/页码/排序方式(0,1,2)　－－> 利用url捕获

# /list？type_id=种类&sort=排序方式　－－>利用request.GET.get()方式捕获

# /list/种类id/页码?sort = 排序方式
# 我们选用这一种，遵循设计restful api
# restful api  -> 请求一种资源
class ListView(View):
	'''列表页'''
	def get(self, request, type_id, page):
		'''返回列表页'''
		try:
			type = GoodsType.objects.get(id = type_id)
		except GoodsType.DoesNotExist:
			# 种类不存在
			return redirect(reverse('goods:index'))

		# 获取商品的分类信息
		types = GoodsType.objects.all()


		sort = request.GET.get('sort')
		# 根据种类获取该种类所有的商品,并进行排序
		if sort == 'sales':
			skus = GoodsSKU.objects.filter(type = type).order_by('-sales')
		elif sort == 'hot':
			skus = GoodsSKU.objects.filter(type = type).order_by('price')
		else:
			sort = 'default'
			skus = GoodsSKU.objects.filter(type = type).order_by('-id')


		# 对得到的sku查询集进行分页
		paginator = Paginator(skus, 10)  #每 １０ 为一页

		try:
			page = int(page)
		except:
			page = 1
		if page > paginator.num_pages:
			page = 1
		# 获取第page页的实例对象
		skus_page = paginator.page(page)

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

		# 获取新品推荐信息(一定是同种类的新品)
		new_skus = GoodsSKU.objects.filter(type = type).order_by('-create_time')[:2]   #减号　是作为降序排列

		# 获取用户购物车中的商品的数目
		user = request.user
		cart_count = 0
		if user.is_authenticated():
			# 用户已经登录
			conn = get_redis_connection('default')
			cart_key = 'cart_%d'%user.id
			cart_count = conn.hlen(cart_key)


		# 组织模板上下文

		context = {'skus_page':skus_page,
					'new_skus':new_skus,
					'type':type,
					'types':types,
					'sort':sort,
					'pages':pages,
					'cart_count':cart_count,}

		# 使用模板
		return render(request, 'list.html', context)












