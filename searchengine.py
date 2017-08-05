#-*- coding:utf-8 -*-
import urllib2
from bs4 import BeautifulSoup
from urlparse import urljoin
import sqlite3  as sqlite
import nn
import re
import jieba
import sys
reload(sys)
sys.setdefaultencoding('utf8')
#mynet=nn.searchnet('nn.db')

#创建一个停用词表
ignorewords = set()
with open('stopwords.txt') as f:
    for line in f:
        word = line.strip()
        ignorewords.add(word)
print len(ignorewords)



class crawler:
    # Initialize the crawler with the name of database
    def __init__(self,dbname):
        self.con=sqlite.connect(dbname)

    def __del__(self):
        self.con.close()

    def dbcommit(self):
        self.con.commit()

    # Auxilliary function for getting an entry id and adding
    # it if it's not present
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


    # 把词存入到location表里
    def addtoindex(self,url,soup):
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

        # 把每个词和url对应起来
        for i in range(len(words)):
            word = words[i]
            if word in ignorewords: continue
            wordid=self.getentryid('wordlist','word',word)
            self.con.execute("insert into wordlocation(urlid,wordid,location) values (%d,%d,%d)" % (urlid,wordid,i))


    # 清除HTML标签
    def gettextonly(self,soup):
        v=soup.string
        if v == None:
            c=soup.contents
            resulttext=''
            for t in c:
                subtext=self.gettextonly(t)
                resulttext += subtext+'\n'
            Text = re.findall(ur"[\u4e00-\u9fa5]",resulttext.decode('utf8'))
            text = "".join(Text).encode('utf8')
            return text
        else:
            return v.strip()

    # 用jieba进行切词
    def separateWords(self,text):
        seg_list = jieba.cut(text)  # 默认是精确模式
        return list(seg_list)


    #检查url是否已经被检索过了
    def isindexed(self,url):
        u = self.con.execute("select rowid from urllist where url = '%s'" % url).fetchone()
        if u != None:
            v = self.con.execute('select * from wordlocation where urlid = %d' %u[0]).fetchone()
            if v != None:
                return True
        return False

    #把网页的链接顺序存到数据库
    def addlinkref(self,urlFrom,urlTo,linkText):
        words=self.separateWords(linkText)
        fromid=self.getentryid('urllist','url',urlFrom)
        toid=self.getentryid('urllist','url',urlTo)
        if fromid==toid: return
        cur=self.con.execute("insert into link(fromid,toid) values (%d,%d)" % (fromid,toid))
        linkid=cur.lastrowid
        for word in words:
            if word in ignorewords: continue
            wordid = self.getentryid('wordlist','word',word)
            self.con.execute("insert into linkwords(linkid,wordid) values (%d,%d)" % (linkid,wordid))

    # Starting with a list of pages, do a breadth
    # first search to the given depth, indexing pages
    # as we go
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
                    for link in links:
                        if ('href' in dict(link.attrs)):
                            url=urljoin(page,link['href'])
                            if url.find("'")!=-1: continue
                            url=url.split('#')[0]  # remove location portion
                            if url[0:4]=='http' and not self.isindexed(url):
                                newpages[url]=1
                            linkText=self.gettextonly(link)
                            self.addlinkref(page,url,linkText)
                    self.dbcommit()
                except:
                    print "Could not parse page %s" % page

            pages=newpages

    #创建数据表
    def createindextables(self):
        self.con.execute('create table urllist(url)')
        self.con.execute('create table wordlist(word)')
        self.con.execute('create table wordlocation(urlid,wordid,location)')
        self.con.execute('create table link(fromid integer,toid integer)')
        self.con.execute('create table linkwords(wordid,linkid)')
        self.con.execute('create index wordidx on wordlist(word)')
        self.con.execute('create index urlidx on urllist(url)')
        self.con.execute('create index wordurlidx on wordlocation(wordid)')
        self.con.execute('create index urltoidx on link(toid)')
        self.con.execute('create index urlfromidx on link(fromid)')
        self.dbcommit()

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

    def test(self):
        wordlist = self.con.execute('select urlid, score from pagerank').fetchall()
        print wordlist

cra = crawler('searchindex.db')
cra.test()
#cra.calculatepagerank()
#cra.createindextables()
#
# pages = ['http://news.bjut.edu.cn/']
#cra.crawl(pages)
