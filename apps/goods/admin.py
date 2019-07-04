from django.contrib import admin

# 导入缓存模块
from django.core.cache import cache

from goods.models import GoodsType,IndexPromotionBanner,IndexGoodsBanner,IndexTypeGoodsBanner
# Register your models here.


# 抽出一个父类，其他的模板类只要继承就可以了
class BaseModelAdmin(admin.ModelAdmin):
	def save_model(self, request, obj, form, change):
		'''新增或更新表中的数据时调用'''
		print('1----------------------------1')

		super().save_model(request, obj, form, change)

		print('2----------------------------2')
		# 发出任务，让celery_worker重新生成首页静态页
		from celery_tasks.tasks import generate_static_index_html
		generate_static_index_html.delay()

		# 清除首页的缓存数据
		cache.delete('index_page_data')

	def delete_model(self, request, obj):
		'''删除表中数据时调用'''
		super().delete_model(request, obj)

		# 发出任务，让celery_worker重新生成首页静态页
		from celery_tasks.tasks import generate_static_index_html
		generate_static_index_html.delay()

		# 清除首页的缓存数据
		cache.delete('index_page_data')

class IndexPromotionBannerAdmin(BaseModelAdmin):
	pass


class GoodsTypeAdmin(BaseModelAdmin):
	pass


class IndexGoodsBannerAdmin(BaseModelAdmin):
	pass


class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
	pass


admin.site.register(GoodsType,GoodsTypeAdmin)
admin.site.register(IndexPromotionBanner,IndexPromotionBannerAdmin)

admin.site.register(IndexGoodsBanner,IndexGoodsBannerAdmin)

admin.site.register(IndexTypeGoodsBanner,IndexTypeGoodsBannerAdmin)













