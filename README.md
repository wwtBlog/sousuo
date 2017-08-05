本文介绍的全文搜索引擎，允许人们在大量文档中搜索一系列单词，并根据文档单词的相关程度进行排名。
### 1. 分词
分词的对象可以是网页也可以是文档
### 1. 建立数据库，这是用到的五张表

wordlist |
---|---
rowid | 
word |
这张表是单词表，会保存单词的id，这是唯一的，每个单词只保存一次。

urllist |
---|---
rowid | 
url |
这张表是url表，可以表示文档的路径id，这是唯一的，每个url只保存一次。
wordlocation |
---|---
rowid | 
urlid |
wordid |
location |
这张表最大，意义也最大，把单词和网页对应起来，对于文档中出现的每一个单词都会在这里对应起来。如不同网页中出现的同一个单词，或者同一个网页中对应的同一个单词都会在这张表中出现，面试问倒了。

link |
---|---
rowid | 
fromid |
toid |

这张表表明了一个文档或者网页到另一个文档或者网页之间的关系。

linkwords |
---|---
wordid | 
linkid |
这张表利用字段wordid和linkid记录了哪些单词与链接实际相关。不过好像没有用到。
### 3. 如何存入数据库，何时存
对于link表在爬虫的时候，就要存入数据库，从一个网页爬到另一个网页，fromid和toid就会填好。
对于word表、url表和wordlocation表，在获取文档内容后添加索引，就是把分词后的结果存入数据库。首先存urlid如果没有就新建一个，然后存wordid，如果没有就新建一个，最后存入wordlocation，把urlid、wordid和location都对应到一个表中。
### 4.小高潮，查询
构造一个查询函数，接收一个查询字符串作为参数，并将其拆分为多个单词，然后构造一个sql查询，账户查询那些包含所有不同单词的url。
例如搜索涉及到两个单词(对应ID WEI 10 和 17)的查询，sql语句如下：

```
select w0.urlid,w0.location,w1.locathion
from wordlocation w0,wordlocation w1
where w0.urlid = w1.urlid
and w0.wordid = 10
and w1.wordid = 17
```
这样每次查询就会返回文档的id，及每个单词的位置，当然重头戏就是对urlid进行排名。
### 5.高潮来了，基于内容的排名。但你会觉得索然无味
通过计算单词频度，单词之间的距离，单词出现在文档中的位置，及高大上的PageRank算法。
### 6.高大上的神经网络算法。
在线应用的一个最大优势就在于，他们会持续收到以用户行为为表现形式的反馈信息。对于搜索引擎而言，每一位用户可以通过值点击某条搜索结果，而不选择点击其他内容，向搜索引擎基石提供关于他对搜索结果的喜好程度的信息。

为此我们需要构造一个人工神经网络，向其提供：查询的单词，返回给用户的搜索结果，以及用户的点击决策，然后再对其加以训练。一旦网络经过许多不同查询的训练之后，我们就可以利用它来改进搜索结果的排序，以更好地反映用户在过去一段时间内的实际点击情况。

详细介绍：
https://zhuanlan.zhihu.com/p/28328164