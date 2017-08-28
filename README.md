
## 数据存储

1.wordlocation表

这个表没有主键，存入的是网页的URLid，切词之后词的id，还有词在网页中的位置。当爬取网页的时候，会经过去掉HTML标签，去掉英文字符，切词的处理，然后就把网页填充到这个表里面。
### 把词存入到location表里
    
```
def addtoindex(self,url,soup):
        #判断这个url之前有没有被索引过
        if self.isindexed(url):
            return
        print 'Indexing '+ url
        # 得到网页中的文本
        text=self.gettextonly(soup)
        if len(text) == 0 or text == None:
            return
        #分词
        words=self.separateWords(text)
        # 得到 URL id
        urlid=self.getentryid('urllist','url',url)
        # 把每个词和url对应起来，存入wordlocation表的过程
        for i in range(len(words)):
            word = words[i]
            if word in ignorewords: continue
            wordid=self.getentryid('wordlist','word',word)
            self.con.execute("insert into wordlocation(urlid,wordid,location) values (%d,%d,%d)" % (urlid,wordid,i))
```


2.wordid和urlid表

存入数据库的时候需要词和url的id，如果不在这个表里，就新建一个。

```
def getentryid(self,table,field,value):
    cur=self.con.execute(
        "select rowid from %s where %s='%s'" % (table,field,value))
    res=cur.fetchone()
    if res==None:
        cur=self.con.execute(
            "insert into %s (%s) values ('%s')" % (table,field,value))
        return cur.lastrowid
    else:
        return res[0]
```

3.link表

在爬取网页的过程中，用的是广度优先的策略，从一个网页爬取到另一个网页时会存入此表。

```
def crawl(self,pages,depth=2):
    for i in range(depth):
        newpages={}
        for page in pages:
            try:
                c=urllib2.urlopen(page)
            except:
                print "Could not open %s" % page
                continue
            try:
                soup=BeautifulSoup(c.read())
                self.addtoindex(page,soup)
                links=soup('a')
                #从本网页得到下一个网页的链接
                for link in links:
                    if ('href' in dict(link.attrs)):
                        url=urljoin(page,link['href'])
                        if url.find("'")!=-1: continue
                        url=url.split('#')[0]  # remove location portion
                        if url[0:4]=='http' and not self.isindexed(url):
                            newpages[url]=1
                        linkText=self.gettextonly(link)
                        #addlinkref即是存入link表的函数
                        self.addlinkref(page,url,linkText)
                self.dbcommit()
            except:
                print "Could not parse page %s" % page

        pages=newpages
```


### 结语

这个类主要是爬取数据，清洗数据，构建数据库，把清洗后的数据存入到数据库中。

## 查询细节

### 根据查询词得到所有相关的网页

把查询词分词，去除停用词，构建查询语句，从构建好的数据库中查找相关网页。

```
def getmatchrows(self,q):
        # 输入查询字符串
        fieldlist='w0.urlid'
        tablelist=''
        clauselist=''
        wordids=[]

        #用结巴对查询词进行切分
        words = list(jieba.cut(q))  # 默认是精确模式
        print ' '.join(words)
        tablenumber=0

        for word in words:
            # 获得 word ID
            wordrow=self.con.execute(
                "select rowid from wordlist where word='%s'" % word).fetchone()
            if wordrow!=None:
                wordid=wordrow[0]
                wordids.append(wordid)
                if tablenumber > 0:
                    tablelist+=','
                    clauselist+=' and '
                    clauselist+='w%d.urlid=w%d.urlid and ' % (tablenumber-1,tablenumber)
                fieldlist+=',w%d.location' % tablenumber
                tablelist+='wordlocation w%d' % tablenumber
                clauselist+='w%d.wordid=%d' % (tablenumber,wordid)
                tablenumber+=1
            else:
                print 'can not find this word'
        if len(wordids) == 0:
            return None,wordids
        # Create the query from the separate parts
        fullquery='select %s from %s where %s' % (fieldlist,tablelist,clauselist)
        print fullquery
        cur=self.con.execute(fullquery)
        rows=[row for row in cur]
        print rows
        return rows,wordids
```


这个方法的主要作用是查询，首先需要构造查询语句，当有两个词的时候构造出来的查询语句如下所示：

```
select w0.urlid,w0.location,w1.location from wordlocation w0,wordlocation w1 
where w0.wordid=328 and w0.urlid=w1.urlid and w1.wordid=96
```

输入是一个查询词，比如“邓小平改革”，这里会分为两个词。
返回的是查询结果
[(1, 494, 117), (42, 298, 340), (56, 183, 73), (56, 183, 303)]
是一个列表，列表中是三元的元组，第一个元素代表url的id，即查到的网页，后面两个代表这两个词出现的位置。
### 衡量网页的质量

从上一个函数我们得到网页还有两个词出现的位置，如果两个词在同一个网页中出现在不同的位置，那么网页会被返回多次，次数越多网页的质量越高。

```
def frequencyscore(self,rows):
    counts=dict([(row[0],0) for row in rows])
    for row in rows: counts[row[0]]+=1
    return self.normalizescores(counts)
```

根据词的位置可以判断网页的优劣，两个词之间的距离越小则网页越好，两个词出现在网页中的位置越靠前网页质量越好。

```
def locationscore(self,rows):
    locations=dict([(row[0],1000000) for row in rows])
    for row in rows:
        loc=sum(row[1:])
        if loc < locations[row[0]]: locations[row[0]]=loc
    return self.normalizescores(locations,smallIsBetter=1)

def distancescore(self,rows):
    # If there's only one word, everyone wins!
    if len(rows[0])<=2: return dict([(row[0],1.0) for row in rows])

    # Initialize the dictionary with large values
    mindistance=dict([(row[0],1000000) for row in rows])

    for row in rows:
        dist=sum([abs(row[i]-row[i-1]) for i in range(2,len(row))])
        if dist<mindistance[row[0]]: mindistance[row[0]]=dist
    return self.normalizescores(mindistance,smallIsBetter=1)
```

### PageRank




```
#计算pagerank值
    def calculatepagerank(self,iterations=20):
        # clear out the current page rank tables
        self.con.execute('drop table if exists pagerank')
        self.con.execute('create table pagerank(urlid primary key,score)')

        # initialize every url with a page rank of 1
        for (urlid,) in self.con.execute('select rowid from urllist'):
            self.con.execute('insert into pagerank(urlid,score) values (%d,1.0)' % urlid)
        self.dbcommit()

        for i in range(iterations):
            print "Iteration %d" % (i)
            for (urlid,) in self.con.execute('select rowid from urllist'):
                pr=0.15

                # Loop through all the pages that link to this one
                for (linker,) in self.con.execute(
                                'select distinct fromid from link where toid=%d' % urlid):
                    # Get the page rank of the linker
                    linkingpr=self.con.execute(
                        'select score from pagerank where urlid=%d' % linker).fetchone()[0]

                    # Get the total number of links from the linker
                    linkingcount=self.con.execute(
                        'select count(*) from link where fromid=%d' % linker).fetchone()[0]
                    pr+=0.85*(linkingpr/linkingcount)
                self.con.execute(
                    'update pagerank set score=%f where urlid=%d' % (pr,urlid))
            self.dbcommit()
```


### 对网页进行排序


```
def query(self,q):
        if q == None or len(q) == 0:
            return
        rows,wordids=self.getmatchrows(q)
        if len(wordids) == 0:
            print '找到不到网页'
            return
        scores=self.getscoredlist(rows,wordids)
        rankedscores=[(score,url) for (url,score) in scores.items()]
        rankedscores.sort()
        rankedscores.reverse()
        for (score,urlid) in rankedscores[0:10]:
            print '%f\t%s' % (score,self.geturlname(urlid))
        return wordids,[r[1] for r in rankedscores[0:10]]
```

## 结语

这个类的主要目的是查询，通过对关键词进行分词得到相关的网页，然后对网页质量进行排序，输出前十个结果。
从点击行为中学习


## 一个点击跟踪网络设计


创建新的数据库


```
#建立输入层、隐藏层和输出层表
def maketables(self):
    self.con.execute('create table hiddennode(create_key)')
    self.con.execute('create table wordhidden(fromid,toid,strength)')
    self.con.execute('create table hiddenurl(fromid,toid,strength)')
    self.con.commit()
```

开始训练

这里训练采取的材料是传统方法的查询词，及返回的十个URL，还有用户的点击情况。
### 首先搭建隐藏层
把词进行分词，然后去掉停用词，排序用“-”连接起来，当做隐藏层的结点，然后设置隐藏层和输入层，隐藏层和输出层的权重值。

```
def generatehiddennode(self,wordids,urls):
    if len(wordids)>3: return None
    # Check if we already created a node for this set of words
    sorted_words=[str(id) for id in wordids]
    sorted_words.sort()
    createkey='_'.join(sorted_words)
    res=self.con.execute(
        "select rowid from hiddennode where create_key='%s'" % createkey).fetchone()
    # If not, create it
    if res==None:
        cur=self.con.execute(
            "insert into hiddennode (create_key) values ('%s')" % createkey)
        hiddenid=cur.lastrowid
        # 设置默认的权重
        for wordid in wordids:
            self.setstrength(wordid,hiddenid,0,1.0/len(wordids))
        for urlid in urls:
            self.setstrength(hiddenid,urlid,1,0.1)
        self.con.commit()

设置权重的方法
def setstrength(self,fromid,toid,layer,strength):
    if layer==0: table='wordhidden'
    else: table='hiddenurl'
    res=self.con.execute('select rowid from %s where fromid=%d and toid=%d' % (table,fromid,toid)).fetchone()
    if res==None:
        self.con.execute('insert into %s (fromid,toid,strength) values (%d,%d,%f)' % (table,fromid,toid,strength))
    else:
        rowid=res[0]
        self.con.execute('update %s set strength=%f where rowid=%d' % (table,strength,rowid))
```

2.根据查询词和返回的URL来激活隐藏结点
查询词作为输入层，返回的URL作为输出层，与查询词相关的隐藏结点，与返回的URL相关的隐藏结点都会被激活，参与到神经网络的训练中去。

```
def getallhiddenids(self,wordids,urlids):
        l1={}
        for wordid in wordids:
            cur=self.con.execute(
                'select toid from wordhidden where fromid=%d' % wordid)
            for row in cur: l1[row[0]]=1
        for urlid in urlids:
            cur=self.con.execute(
                'select fromid from hiddenurl where toid=%d' % urlid)
            for row in cur: l1[row[0]]=1
        return l1.keys()
```

3.生成用于训练的神经网络
查询词作为输入层，返回的URL作为输出层，与两者相关的结点作为隐藏层。这样一个神经网络就搭建起来了。

```
def setupnetwork(self,wordids,urlids):
        # value lists
        self.wordids=wordids
        self.hiddenids=self.getallhiddenids(wordids,urlids)
        self.urlids=urlids

        # node outputs
        self.ai = [1.0]*len(self.wordids)
        self.ah = [1.0]*len(self.hiddenids)
        self.ao = [1.0]*len(self.urlids)

        # 创建权重矩阵
        self.wi = [[self.getstrength(wordid,hiddenid,0)
                    for hiddenid in self.hiddenids]
                   for wordid in self.wordids]
        self.wo = [[self.getstrength(hiddenid,urlid,1)
                    for urlid in self.urlids]
                   for hiddenid in self.hiddenids]
```

4.前馈法

```
def feedforward(self):
        # 唯一的输入查询词，将查询词所在结点激活
        for i in range(len(self.wordids)):
            self.ai[i] = 1.0

        # 将隐藏结点激活
        for j in range(len(self.hiddenids)):
            sum = 0.0
            for i in range(len(self.wordids)):
                sum = sum + self.ai[i] * self.wi[i][j]
            self.ah[j] = tanh(sum)

        # 将值传递到输出结点
        for k in range(len(self.urlids)):
            sum = 0.0
            for j in range(len(self.hiddenids)):
                sum = sum + self.ah[j] * self.wo[j][k]
            self.ao[k] = tanh(sum)

        return self.ao[:]
```

5.点击行为产生误差反向传播
targets=[0.0]*len(urlids)
targets[urlids.index(selectedurl)]=1.0
代码中的selecturl为点击的那个URL，将点击的那个URL置为1.0，其他置为0，与输出层结点值的差值作为误差反向传播。

```
def backPropagate(self, targets, N=0.5):
    # 计算输出层的误差
    output_deltas = [0.0] * len(self.urlids)
    for k in range(len(self.urlids)):
        error = targets[k]-self.ao[k]
        output_deltas[k] = dtanh(self.ao[k]) * error

    # calculate errors for hidden layer
    hidden_deltas = [0.0] * len(self.hiddenids)
    for j in range(len(self.hiddenids)):
        error = 0.0
        for k in range(len(self.urlids)):
            error = error + output_deltas[k]*self.wo[j][k]
        hidden_deltas[j] = dtanh(self.ah[j]) * error

    # update output weights
    for j in range(len(self.hiddenids)):
        for k in range(len(self.urlids)):
            change = output_deltas[k]*self.ah[j]
            self.wo[j][k] = self.wo[j][k] + N*change

    # update input weights
    for i in range(len(self.wordids)):
        for j in range(len(self.hiddenids)):
            change = hidden_deltas[j]*self.ai[i]
            self.wi[i][j] = self.wi[i][j] + N*change
```

6.训练好的模型可作为衡量网页质量好坏的标准
由上一篇文章可知，通过查询词可获得一批文章，但是需要对网页质量进行排序，那么我们拿到查询词，拿到输出的URL，生成中间节点就可以通过前馈法进行传播，生成结果作为得分。

```
def getresult(self,wordids,urlids):
    self.setupnetwork(wordids,urlids)
    return self.feedforward()
```
