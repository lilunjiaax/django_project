from django.shortcuts import render,redirect

from django.http import JsonResponse

from django.core.urlresolvers import reverse

from django.views.generic import View

# 导入事务控制模块
from django.db import transaction

from django.conf import settings

import os

from goods.models import GoodsSKU

from order.models import OrderInfo,OrderGoods
# 导入用户模块的地址模型类
from user.models import Address

from django_redis import get_redis_connection

from utils.mixin import LoginRequiredMixin

from datetime import datetime



# 导入支付宝接口包
from alipay import Alipay

# Create your views here.

# /order/place
# 接受的是cart.html中的一个post请求，
class OrderPlaceView(LoginRequiredMixin, View):
	'''提交订单页显示'''
	def post(self, request):
		'''订单页'''
		user = request.user
		# 获取参数sku_ids
		sku_ids = request.POST.getlist('sku_ids')

		# 校验参数
		if not sku_ids:
			# 跳转到购物车页面
			return redirect(reverse('cart:show'))

		conn = get_redis_connection('default')
		cart_key = 'cart_%d'%user.id

		skus = []
		total_count = 0
		total_price = 0
		# 遍历sku_ids
		for sku_id in sku_ids:
			sku = GoodsSKU.objects.get(id = sku_id)
			# 获取用户所要购买的商品的数量
			count = conn.hget(cart_key, sku_id)
			# 计算商品的小计
			amount = int(count)*sku.price
			# 给sku添加属性
			sku.count = count
			sku.amount = amount

			skus.append(sku)
			total_count += int(count)
			total_price += amount
		# 运费：实际开发时，会有一个运费计算子系统，
		transit_price = 10

		# 实付款
		total_pay = total_price+transit_price

		# 获取用户的收件地址
		addrs = Address.objects.filter(user = user)

		sku_ids = ','.join(sku_ids) # [1,2,3] --> '1,2,3'
		# 组织上下文
		context = {
		'skus':skus,
		'total_count':total_count,
		'total_price':total_price,
		'transit_price':transit_price,
		'total_pay':total_pay,
		'addrs':addrs,
		'sku_ids':sku_ids
		}
		return render(request, 'place_order.html', context)


# 创建订单
# /order/commit
class OrderCommitView(View):
	'''订单创建'''
	#此装饰器的作用是将函数里面所有的sql操作都放在一个事务里面
	@transaction.atomic  
	def post(self, request):
		'''订单创建'''
		user = request.user
		if not user.is_authenticated():
			# 用户未登录
			return JsonResponse({'res':0,'errmsg':'用户未登录'})
		# 接受参数
		addr_id = request.POST.get('addr_id')
		pay_method = request.POST.get('pay_method')
		sku_ids = request.POST.get('sku_ids')

		if not all([addr_id,pay_method,sku_ids]):
			return JsonResponse({'res':1,'errmsg':'参数不完整'})

		# 校验支付方式
		if pay_method not in OrderInfo.PAY_METHODS.keys():
			return JsonResponse({'res':2,'errmsg':'非法的支付方式'})

		# 检验地址
		try:
			addr = Address.objects.get(id = addr_id)
		except Address.DoesNotExist:
			# 地址不存在
			return JsonResponse({'res':3,'errmsg':'地址非法'})


		# todo:创建订单核心业务
		'''
		缺少的参数：order_id,total_count,total_price,transit_price
		'''
		# 订单id我们采用年月日时分秒+用户id来生成
		order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)

		# 运费
		transit_price = 10

		# 总数目和总净额
		total_count = 0
		transit_price = 0

		# 设置保存点
		save_id = transaction.savepoint()
		try:
			# todo:向df_order_info表中增加一条记录
			order = OrderInfo.objects.create(order_id = order_id,
									user = user,
									addr = addr,
									pay_method = pay_method,
									total_count = total_count,
									total_price = total_price,
									transit_price = transit_price)

			# todo:用户订单中有几个商品，就向df_order_goods中加入几条记录
			conn = get_redis_connection('default')
			cart_key = 'cart_%d'%user.id

			sku_ids = sku_ids.split(',')
			for sku_id in sku_ids:
				for i in range(3):
					# 获取商品信息
					try:
						# 悲观锁
						# select * from df_goods_sku where id = sku_id for update
						sku = GoodsSKU.objects.select_for_update().get(id = sku_id)
					except:
						# 商品不存在
						# 需要回滚到保存点
						transaction.savepoint_rollback(save_id)
						return JsonResponse({'res':4,'errmsg':'商品不存在'})

					# 从redis中获取用户购买商品的数量
					count = conn.hget(cart_key, sku_id)

					# 需要判断商品的库存（防止两人同时下单，一人先将库存买完）
					if int(count) > sku.stock:
						# 库存不足，需要回滚事务
						transaction.savepoint_rollback(save_id)
						return JsonResponse({'res':6, 'errmsg':'商品库存不足'})

					# 修改商品的库存和销量
					orgin_stock = sku.stock
					new_stock = orgin_stock -= int(count)
					new_sales = sku.stock += int(count)

					# sql语句为：update de_goods_sku set (stock = new_stock,sales = new_sales) where id = sku_id and stock = orgin

					# 返回的res代表被修改的行数
					res = GoodsSKU.objects.filter(id = sku_id, stock = orgin).update(stock=new_stock,sales = new_sales)
					if res == 0:
						if i == 2:
							# 尝试了第三次
							transaction.savepoint_rollback(save_id)
							return JsonResponse({'res':7,'errmsg':'购买失败'})
						continue
				# sku.stock -= int(count)
				# sku.sales += int(count)
				# sku.save()

				# todo:向表中添加一条记录
				OrderGoods.objects.create(order = order,
										sku = sku,
										count = count,
										price = sku.price)



				# 累加计算订单商品的总数量和总价格
				amount = sku.price*int(count)
				total_count += int(count)
				total_price += amount

			# 更新订单信息表中的商品总数量和总价格
			order.total_count = total_count
			order.total_price = total_price
			order.save()
		except Exception as e:
			transaction.savepoint_rollback(save_id)
			return JsonResponse({'res':7,'errmsg':'下单失败'})

		# 提交事务
		transaction.savepoint_commit(save_id)
		# 清除用户购物车中对应的记录
		conn.hdel(cart_key, *sku_ids) #要对列表进行拆包处理
		# 返回应答
		return JsonResponse({'res':5,'message':'创建成功'})


# 订单支付
# 前端传递的参数　订单id(order_id)
#  /order/pay
class OrderPayView(View):
	'''订单支付'''
	def post(self, request):
		'''订单支付'''

		# 用户是否登录
		user = request.user
		if not user.is_authenticated():
			return JsonResponse({'res':0,'errmsg':'用户未登陆'})

		# 接收参数
		order_id = request.POST.get('order_id')

		# 校验参数
		if not order_id:
			return JsonResponse({'res':1,'errmsg':'无效的订单id'})
		
		try:  #查出的订单必须要符合id相同，用户相同，支付方式为３，订单状态为：未支付
			order = OrderInfo.objects.get(order_id = order_id,
											user = user,
											pay_method = 3,
											order_status = 1)
		except OrderInfo.DoesNotExist:
			return JsonResponse({'res':1,'errmsg':订单错误})

		# 业务处理：使用python sdk调用支付宝的支付接口


		# 初始化
		alipay = Alipay(
			appid = "2016093000628658", #自己沙箱中的APPID
			app_notify_url = None, #默认的回调url
			app_private_key_path = os.path.join(settings.BASE_DIR,'apps/order/app_private_key.pem'),
			alipay_public_key_path = os.path.join(settings.BASE_DIR,'apps/order/alipay_public_key.pem'),
			sign_type = "RSA2",  #RSA或者RSA2
			debug = "True"  #沙箱模式就是调试模式
			)
		# 调用支付接口
		# 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
		total_pay = order.total_price + order.transit_price  #Decimal类型，无法序列化
		order_string = alipay.api_alipay_trade_page_pay(
			out_trade_no = order_id,#订单号
			total_amount = str(total_pay), #原本是Decimal数据类型，无法序列化Json形式，只能先转化为str
			subject = '天天生鲜%s'%order_id, #标题
			return_url = None,
			notify_url = None #都不填，因为我们现在没有公网ip
			)

		# 返回应答
		pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
		return JsonResponse({'res':3,'pay_url':pay_url})



# Ajax post
# /order/check
# 参数：order_id
class CheckPayView(View):
	'''查看订单支付结果'''
	def post(self,request):
		# 用户是否登录
		user = request.user
		if not user.is_authenticated():
			return JsonResponse({'res':0,'errmsg':'用户未登陆'})

		# 接收参数
		order_id = request.POST.get('order_id')

		# 校验参数
		if not order_id:
			return JsonResponse({'res':1,'errmsg':'无效的订单id'})
		
		try:  #查出的订单必须要符合id相同，用户相同，支付方式为３，订单状态为：未支付
			order = OrderInfo.objects.get(order_id = order_id,
											user = user,
											pay_method = 3,
											order_status = 1)
		except OrderInfo.DoesNotExist:
			return JsonResponse({'res':1,'errmsg':订单错误})

		# 业务处理：使用python sdk调用支付宝的支付接口


		# 初始化
		alipay = Alipay(
			appid = "2016093000628658", #自己沙箱中的APPID
			app_notify_url = None, #默认的回调url
			app_private_key_path = os.path.join(settings.BASE_DIR,'apps/order/app_private_key.pem'),
			alipay_public_key_path = os.path.join(settings.BASE_DIR,'apps/order/alipay_public_key.pem'),
			sign_type = "RSA2",  #RSA或者RSA2
			debug = "True"  #沙箱模式就是调试模式
			)

		# 调用支付宝的交易查询接口（可传两个参数，out_trade_no订单号；trade_no,支付宝交易号，二者只需一个即可）
		while True:
			response = alipay.api_alipay_trade_query(order_id)
			# response是一个字典

			code = response.get('code') #查看借口是否调用成功
			if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
				# 支付成功
				# 获取支付宝交易号
				trade_no = response.get('trade_no')
				# 更新订单状态
				order.trade_no = trade_no
				order.order_status = 4  #处于待评价状态
				order.save()
				# 返回结果
				return JsonResponse({'res':3,'errmsg':'支付成功'})
			elif code == '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
				# 等待买家付款
				# 业务处理失败，一会就会处理成功
				import time
				time.sleep(5)
				continue
			else:
				# 支付出错
				return JsonResponse({'res':4,'errmsg':'支付失败'})
			

class CommentView(View):
	'''订单评论'''
	def get(self,request,order_id):
		'''提供评论页面'''
		user = request,user

		# 校验数据
		if not order_id:
			return redirect(reverse('user:order'))

		try:
			order = OrderInfo.objects.get(order_id = order_id,user = user)
		except:
			OrderInfo.DoesNotExist:
			return redirect(reverse('user:order'))
		# 获取订单状态
		order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
		# 获取订单商品信息
		order_skus = OrderGoods.objects.filter(order_id = order_id)
		for order_sku in order_skus:
			# 计算商品小计
			amount = order_sku.price * order_sku.count
			order_sku.amount = amount

		# 动态的给order增加order_skus属性，这样可以通过：order.order_skus遍历
		order.order_skus = order_skus

		# 使用模板
		return render(request, 'order_comment.html', {'order':order})













