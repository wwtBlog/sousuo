#-*- coding:utf-8 -*-
import sqlite3  as sqlite
import jieba

class searcher:
    def __init__(self,dbname):
        self.con=sqlite.connect(dbname)

    def __del__(self):
        self.con.close()

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
        #select w0.urlid,w0.location,w1.location from wordlocation w0,wordlocation w1
        #where w0.wordid=328 and w0.urlid=w1.urlid and w1.wordid=96
        print fullquery
        cur=self.con.execute(fullquery)
        rows=[row for row in cur]
        print rows
        return rows,wordids

    def getscoredlist(self,rows,wordids):
        totalscores=dict([(row[0],0) for row in rows])

        # This is where we'll put our scoring functions
        weights=[(1.0,self.locationscore(rows)),
                 (1.0,self.frequencyscore(rows)),
                 (1.0,self.pagerankscore(rows))]
                 #(1.0,self.linktextscore(rows,wordids)),
                 #(5.0,self.nnscore(rows,wordids))]
        for (weight,scores) in weights:
            for url in totalscores:
                totalscores[url]+=weight*scores[url]
        return totalscores

    def geturlname(self,id):
        return self.con.execute(
            "select url from urllist where rowid=%d" % id).fetchone()[0]

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

    def normalizescores(self,scores,smallIsBetter=0):
        vsmall=0.00001 # Avoid division by zero errors
        if smallIsBetter:
            minscore=min(scores.values())
            return dict([(u,float(minscore)/max(vsmall,l)) for (u,l) in scores.items()])
        else:
            maxscore=max(scores.values())
            if maxscore==0: maxscore=vsmall
            return dict([(u,float(c)/maxscore) for (u,c) in scores.items()])

    def frequencyscore(self,rows):
        counts=dict([(row[0],0) for row in rows])
        for row in rows: counts[row[0]]+=1
        return self.normalizescores(counts)

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

    def inboundlinkscore(self,rows):
        uniqueurls=dict([(row[0],1) for row in rows])
        inboundcount=dict([(u,self.con.execute('select count(*) from link where toid=%d' % u).fetchone()[0]) for u in uniqueurls])
        return self.normalizescores(inboundcount)

    def linktextscore(self,rows,wordids):
        linkscores=dict([(row[0],0) for row in rows])
        for wordid in wordids:
            cur=self.con.execute('select link.fromid,link.toid from linkwords,link where wordid=%d and linkwords.linkid=link.rowid' % wordid)
            for (fromid,toid) in cur:
                if toid in linkscores:
                    pr=self.con.execute('select score from pagerank where urlid=%d' % fromid).fetchone()[0]
                    linkscores[toid]+=pr
        maxscore=max(linkscores.values())
        normalizedscores=dict([(u,float(l)/maxscore) for (u,l) in linkscores.items()])
        return normalizedscores

    def pagerankscore(self,rows):
        pageranks=dict([(row[0],self.con.execute('select score from pagerank where urlid=%d' % row[0]).fetchone()[0]) for row in rows])
        maxrank=max(pageranks.values())
        normalizedscores=dict([(u,float(l)/maxrank) for (u,l) in pageranks.items()])
        return normalizedscores

    def nnscore(self,rows,wordids):
        # Get unique URL IDs as an ordered list
        urlids=[urlid for urlid in dict([(row[0],1) for row in rows])]
        nnres = mynet.getresult(wordids,urlids)
        scores = dict([(urlids[i],nnres[i]) for i in range(len(urlids))])
        return self.normalizescores(scores)

search = searcher('searchindex.db')
search.getmatchrows('共产党指导学校')
