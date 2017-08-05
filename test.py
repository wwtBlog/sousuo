#-*- coding:utf-8 -*-
import jieba


seg_list = jieba.cut("他来到了网易杭研大厦")  # 默认是精确模式
for seg in seg_list:
    print seg