from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client

from django.conf import settings

class FDFSStorage(Storage):
	'''fast dfs 文件存储类'''
	def __init__(self, client_conf = None, base_url = None):
		'''初始化传参'''
		if client_conf is None:
			client_conf = settings.FDFS_CLIENT_CONF
		self.client_conf = client_conf

		if base_url is None:
			base_url = settings.FDFS_URL
		self.base_url = base_url

	def _open(self, name, mode = 'rb'):
		'''打开文件时使用'''
		pass

	def _save(self, name, content):
		'''保存文件时使用'''
		# name:你选择的上传文件的名字
		# content:包含你上传文件内容的File对象

		# 目标就是将content上传到fastDFS

		# 创建一个Fdfs_client对象
		# 注意：client.conf的路径一定是相对于项目根目录的路径。
		client = Fdfs_client(self.client_conf)

		# 上传文件到fast_dfs系统中（在这里我们上传的对象是 File对象，包含内容）
		res = client.upload_by_buffer(content.read())
		# 返回的 res 是一个字典
		'''
		dict
		{
			'Group name':group_name,
			'Remote file_id':remote_file_id,
			'Status':'Upload successed',
			'Local file name':'',
			'Uploaded size':upload_size,
			'Storage IP':storage_ip
		}
		'''
		if res.get('Status') != 'Upload successed.':
			# 上传失败
			raise Exception('上传文件到fast dfs失败')

		# 返回文件id
		filename = res.get('Remote file_id')

		# _save()函数返回的内容就是我们传递个image数据表的值
		return filename 


	def exists(self, name):
		'''Django判断文件名是否可用'''
		# 可用返回False , 不可用返回 True
		# 而我们没有保存文件名在Django系统中，所以文件名一直可用
		return False


	def url(self, name):
		'''返回访问文件的url路径'''
		return self.base_url + name















