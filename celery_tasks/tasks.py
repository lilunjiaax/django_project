# 使用celery
import time
from celery import Celery

from django.conf import settings

from django.core.mail import send_mail

# 在任务处理者端加代码
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
django.setup()

# 类的导入必须放在初始化的下面，否则会报找不到的错误
from goods.models import GoodsType,IndexGoodsBanner,IndexTypeGoodsBanner,IndexPromotionBanner
from django_redis import get_redis_connection

# 加载模板文件模块
from django.template import loader, RequestContext

# 创建实例对象
app = Celery('celery_tasks.tasks', broker = 'redis://127.0.0.1:6379/8')


# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
	"""发送激活邮件"""
	# 组织邮件信息
	subject = '天天生鲜欢迎信息'
	message = ''
	# 当发送信息中有标签时，使用html_message方式传输
	html_message = '''<h1>%s, 欢迎</h1>点击链接，激活账户.<br><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>'''%(username,token,token)
	sender = settings.EMAIL_FROM
	receiver = [to_email]
	send_mail(subject, message, sender, receiver,html_message = html_message)
		

# 想要成为celery任务，必须要使用装饰器
@app.task
def generate_static_index_html():
	'''产生首页静态页面'''

	# 获取商品的种类信息
	types = GoodsType.objects.all()

	# 获取首页轮播商品信息
	goods_banners = IndexGoodsBanner.objects.all().order_by('index')

	# 获取首页促销活动信息
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

	# 组织末班上下文
	context = {'types':types,
			   'goods_banners':goods_banners,
			   'promotion_banners':promotion_banners}

	# 使用模板
	# 1.加载模板文件，返回模板对象
	temp = loader.get_template('static_index.html')
	
	# 2.定义模板上下文,由于类中并无request参数，所有建议这一步省略
	# context = RequestContext(request, context)

	# 3.模板渲染，直接传入字典，也可以替换模板里面的值
	static_index_html = temp.render(context)
	
	# 生成首页对象
	save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
	with open(save_path, 'w') as f:
		f.write(static_index_html)



