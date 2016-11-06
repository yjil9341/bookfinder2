from multiprocessing import Pool, Lock, Manager
import multiprocessing
import time
import urllib
import requests
import sys
import random
import os
from requests.exceptions import ConnectTimeout
from requests.exceptions import ReadTimeout
from requests.exceptions import ChunkedEncodingError
from requests.exceptions import ProxyError
from requests.exceptions import ConnectionError
from requests.exceptions import ContentDecodingError
from requests.exceptions import TooManyRedirects
from functools import partial
from bs4 import BeautifulSoup
import re
import pandas as pd
from functools import partial
from tqdm import *
import datetime
import settings
from urlparse import urlparse

##If i am not reading itemcontainers correctly that means, propbably there was nothing read after entering the right url or i entered the wrong url
#My code ignores for somereason if itemcontainers not read properly, change this

##Also thre is a case where len(lst )== 0 , 0, 0, 0,
##Fix this as well


def format_url(url):
    # make sure URLs aren't relative, and strip unnecssary query args
    u = urlparse(url)

    scheme = u.scheme or "https"
    host = u.netloc or "www.amazon.com"
    path = u.path

    if not u.query:
        query = ""
    else:
        query = "?"
        for piece in u.query.split("&"):
            k, v = piece.split("=")
            if k in settings.allowed_params:
                query += "{k}={v}&".format(**locals())
        query = query[:-1]
    return "{scheme}://{host}{path}{query}".format(**locals())



#*#Uses proxy.txt proxies which is saved from running get_proxy() in the beginning of the code run
def get_proxy_saved():
    f = open('proxies.txt','r')
    text = f.readlines()
    freshproxlist = []
    for line in text:
        prox =  {'http':'http://'+ line.strip() +'/'}
        freshproxlist.append( prox )
    return freshproxlist




#Goes to gatherproxies.com to obtain fresh list of proxies of about 90 proxies.
#Using this function too much withh make me banned from the site, use cautiously,gently.
def get_proxy():
    ports = ['8080','80','3128','8888','81']
    proxlst = []
    proxycleanlst = []
    for port in tqdm(ports):
        url = 'http://gatherproxy.com/embed/?t=Elite&p=' + port + '&c='
        proxlst_saved = get_proxy_saved()
        while True:
            try:
                randomlst = [0,1,2]
                if random.choice(randomlst) != 0:
                    prox  = random.choice(proxlst_saved)
                    response = requests.get(url, headers=settings.headers,proxies = prox,  timeout = (1,5))
                else: response = requests.get(url, headers=settings.headers,  timeout = (1,5))
                if response.status_code != 200:
                    try: proxlst_saved.remove(prox)
                    except: proxlst_saved = get_proxy_saved()
                    continue
                else: break
            except:
                print "Something wrong grabbing proxies"
                pass
            
        html = response.content
        soup = BeautifulSoup(html,'html.parser')
        try:
            proxlstraw = soup.find_all('script',attrs={'type':'text/javascript'})
            proxlstraw = soup.find_all('script',attrs={'type':'text/javascript'})[3:len(proxlstraw)-3]
        except: print "Something wrong during scriping proxies from gatherproxy"
            
        
        for proxraw in proxlstraw:
            proxraw = unicode(proxraw.string).strip()
            beg = '"PROXY_IP":"'
            end = '","PROXY_LAST_UPDATE":'
            try:
                proxclean =  proxraw[proxraw.index(beg)+len(beg):proxraw.index(end)] + ':' + port
                proxlst.append({'http':'http://' + str(proxclean)})
                proxycleanlst.append(proxclean)
            except: print "proxclean not properly read: Error arising from get_proxy()"
    f = open('proxies.txt','w')
    for proxy in proxycleanlst: f.write(proxy +'\n')
    f.close
    return proxlst

#*#Uses preexisting proxies to simultaneously check for internet conenction/ obtain html.
def wait_for_internet_connection(ur):
    proxlst = get_proxy_saved()
    while True:
        try:
            response = requests.get(ur, headers= settings.headers, proxies = random.choice(proxlst), timeout = (1,5))
            if len(response.content) < 100000:
##                print "wait_for_internet_connection: len(html) < 100000"
                continue
            else: return response
        except: print "Internect Connection Not Properly Initiated, Retrying..."
            
#*#Goes into the directory defined by path, and obtains names + extention of all files in the directory.        
def filename_extractor(path):
    lst = []
    files = os.listdir(path)
    for filename in files: lst.append(filename[:len(filename)-4])
    return lst

#*#Randomly chooses whether to obtain fresh proxies or use proxies from saved file.
#This must be done to ensure I am gently using gather_proxy, but also not reusing useless/banned proxies
def random_proxylst_choice():
    randomlst = [0,1,2,3,4,5,6,7,8,9]
    if random.choice(randomlst) == 0: return get_proxy()
    else: return get_proxy_saved()

#*#Enters url in question then successfully obtain/return soup object.
def proxy_loop(url,sharedproxs):
    while True:
        try:
            proxy = random.choice(sharedproxs)
            response = requests.get(url, headers = settings.headers, proxies = proxy, timeout = (1,5))
            html = response.content
            if len(html) < 100000:
                if len(sharedproxs) == 0:
                    for prox in random_proxylst_choice(): sharedproxs.append(prox)
                else:
                    try: sharedproxs.remove(proxy)
                    except ValueError: pass
                print "Proxies Left %s"  %len(sharedproxs)
                continue
            else: pass
            print 'Success! %s len(html) %s' % (proxy,len(html))
            soup = BeautifulSoup(html,'html.parser')
            break
        ## Unbound local error, "proxy' referenced before assignment == No sharedproxs content
        except (IndexError,UnboundLocalError):
            for prox in random_proxylst_choice(): sharedproxs.append(prox)
            print "Proxies Left %s: IndexError, UnBoundError"  %len(sharedproxs)

        except (ConnectTimeout,ReadTimeout,ChunkedEncodingError,ProxyError,ConnectionError,ContentDecodingError,TooManyRedirects):
            if len(sharedproxs) == 0:
                for prox in random_proxylst_choice(): sharedproxs.append(prox)
            else: 
                try: sharedproxs.remove(proxy)
                except ValueError: pass
            print "Proxies Left %s: All Error"  %len(sharedproxs)
    delay = .5
    time.sleep(delay)
    return soup


#After checking that trade in price is higher than the selling price by fixed amount.
#this function goes into the actual used/new price data.
#Then checks to see if each price listed on Amazon is profitable by checking profitable conditions.
def check_profitable(url,sharedproxs,tradeinpr):
    try:
        soup = proxy_loop(url, sharedproxs)
        ## The first two rows doesn't contain data we want (contains headers..), I have to look into why.
        pricelst = []
        primelst = []
        descriptionlst = []
        conditionlst = []

        sellerlst = []
        ratinglst = []
        ratingnumlst = []

    ##    print "Soup type is: %s" %soup
        print "Accesing itemContainers"
        try: itemContainers = soup.find_all('div',attrs={'class':'a-row a-spacing-mini olpOffer'})
        except:
            print "Something wrong while reading itemContainers"
            quit()
        print "len(itemContainers)", len(itemContainers)
        
        for itemContainer in itemContainers:
            try:
                priceContainer = itemContainer.find('div',attrs={'class':'a-column a-span2 olpPriceColumn'})
                shippingAndTax = priceContainer.find('p',attrs={'class':'olpShippingInfo'})
            except: print 'There is no priceContainer and/or shippingAndTax'
            
            try: shipping = float(shippingAndTax.find('span',attrs={'class':'olpShippingPrice'}).string.strip().replace('$',''))
            except: shipping= 0


            sellerAndRating = itemContainer.find('div', attrs={'class':'a-column a-span2 olpSellerColumn'})
            try:
                seller_raw = sellerAndRating.find('h3',attrs={'class':'a-spacing-none olpSellerName'})
                seller_raw = seller_raw.find('span',attrs={'class':'a-size-medium a-text-bold'})
                seller = seller_raw.find('a').string.strip()
                seller = unicode(seller).encode('ascii', 'ignore')
                sellerlst.append(seller)
            except:
                seller = 'Amazon'
                sellerlst.append(seller)
                print 'No seller or Amazon or Error'
                
            try:
                rating_raw = sellerAndRating.find('p',attrs={'class':'a-spacing-small'})
                rating_raw = rating_raw.find('b').string.strip()
                rating = rating_raw.split()[0]
                ratinglst.append(rating)
            except:
                rating = '100%'
                ratinglst.append(rating)
                print 'No rating or Amazon'

            ratingnumlst.append('100.00')
            
            
                
    ##        print "Item type is: %s" %itemContainer
            if itemContainer.find_all('i',attrs={'class':'a-icon a-icon-prime'}) == []: 
                price_raw = priceContainer.find('span',attrs={'class':'a-size-large a-color-price olpOfferPrice a-text-bold'}).string.strip().replace('$','').replace(',','')
                price = float(price_raw)
                if seller in ['apex_media','Bookbyte Textbooks','RentU']: tax = 0.06
                else: pass
                price = price + price*0.06
                price = price + shipping 
                prime = ''
                pricelst.append(price)
                primelst.append(prime)
            else:
                price_raw = priceContainer.find('span',attrs={'class':'a-size-large a-color-price olpOfferPrice a-text-bold'}).string.strip().replace('$','').replace(',','')
                price = float(price_raw)
                if seller in ['apex_media','Bookbyte Textbooks','RentU']: tax = 0.06
                else: pass
                price = price + price*0.06
                price = price + shipping 
                prime = "(Prime)"
                pricelst.append(price)
                primelst.append(prime)
            
            
                
            try: descripAndCond = itemContainer.find('div', attrs={'class':'a-column a-span3 olpConditionColumn'})
            except: print "There was something wrong while reading descrpAndCond"

    ##        print "descripAndCond is: %s" %descripAndCond
            if descripAndCond.find_all('div',attrs={'class':'comments'}) != []:
                try:
                    description =  descripAndCond.find_all('div',attrs={'class':'comments'})
                    description =  descripAndCond.find_all('div',attrs={'class':'comments'})[len(description)-1]
                except: print "There is something wrong with description"
                
                if description.find('div',attrs={'class':'expandedNote'}) == None: description =  description.string.strip()
                else:
                    try: description = description.find('div',attrs={'class':'expandedNote'}).contents[0].strip()
                    except: print "something wrong with scrqaping description"
                description = unicode(description).encode('ascii', 'ignore')
                descriptionlst.append(description)
            else:
                description = ''
                descriptionlst.append(description)

            try:
                condition_raw = descripAndCond.find('span',attrs={'class':'a-size-medium olpCondition a-text-bold'}).string.strip().replace(' ','').replace('\n','')
                condition = unicode(condition_raw).encode('ascii','ignore')
                conditionlst.append(condition)
            except:
                condition = 'No Condition is being read'
                conditionlst.append(condition)
                print 'No condition or Error'
                
        print "Printing the lens of all the lsts"
        if len(descriptionlst) == 0 and len(descriptionlst) == len(conditionlst) == len(sellerlst) == len(pricelst) == len(ratinglst) == len(ratingnumlst):
            print "len(descriptionlst) == len(conditionlst) == len(sellerlst) == len(pricelst) == len(ratinglst) == len(ratingnumlst)==0 quitting program"
            quit()
        else: pass
        
        if len(descriptionlst) == len(conditionlst) == len(sellerlst) == len(pricelst) == len(ratinglst) == len(ratingnumlst): pass
        else:
            print 'Length of stoerd lists do not match, Something is wrong, figure this out!'
            sys.exit()
                     
        filtered_result = []
        print "len(pricelst)", len(pricelst)
        for i in range(0,len(pricelst)):
            summary = descriptionlst[i].lower()
            profit = tradeinpr-pricelst[i]
            ROI = int(round(profit/pricelst[i]*100))

            if profit < 5: continue
            elif 'international' in summary or 'economy edition' in summary or 'int. edition' in summary or "int'l edition" in summary or 'intl edition' in summary \
                or 'instructor' in summary or 'binding is damaged' in summary or 'special binding' in summary or 'indian edition' in summary or 'binder' in summary \
                or 'loose leaf' in summary or 'special binding' in summary or 'global edition' in summary or 'looseleaf' in summary or 'ebook' in summary  \
                or 'water damage' in summary or 'liquid damage' in summary or 'study guide' in summary or 'studyguide' in summary or "teacher's edition" in summary \
                or 'teachers edition' in summary or 'reprint' in summary or 'missing front and back cover' in summary or "loose-leaf" in summary or "vintage edition" in summary \
                or 'same content as student' in summary or 'annotated' in summary or 'comp copy' in summary or 'pdf' in summary or 'access code only' in summary \
                or 'custom edition' in summary or 'e-book' in summary: continue
            elif sellerlst[i] in ['RAY Books Ltd.','collegebooksdirect','vipulbookstore','Delhi6']: continue 
            elif 'acceptable' in conditionlst[i].lower() : continue
    ##        elif ratingnumlst[i] == 'No Rating' and primelst[i] != "(Prime)": continue
            else: filtered_result.append([ primelst[i] + ' [' + conditionlst[i] + '] ' +  descriptionlst[i], pricelst[i], tradeinpr, '<font color="green"><b>'+ str(profit) + '</b></font>', str(ROI)+'%',  sellerlst[i], ratinglst[i] + '<br>' +  ratingnumlst[i]])
            print "Item should be recorded into html"
            print [ primelst[i] + ' [' + conditionlst[i] + '] ' +  descriptionlst[i], pricelst[i], tradeinpr, '<font color="green"><b>'+ str(profit) + '</b></font>', str(ROI)+'%',  sellerlst[i], ratinglst[i] + '<br>' +  ratingnumlst[i]]
        return filtered_result
    except:
        print "Something wring with check_profit"
        return [[]]



#Searches ISBNS in groups, then creates list of urls by number of pages generated.
#Then checks if the books are profitable by looking at the lowest list price/trade-in price
def fetch_url(url,sharedproxs):
    data = []
    url = format_url(url)
    soup = proxy_loop(url,sharedproxs[0])
    
    #Grabs all rows containing a book.
    count = 0
##    print "Soup type: %s" %soup
    try: divs = soup.find_all('li', attrs = {'class':'s-result-item celwidget'})
    except: print "There was something wrong with reading individual items"

##    print "Type div: %s" %divs
    for div in divs:
        if div.find_all('a',attrs={'class':'s-access-detail-page'}) == []:
            print 'There is something wrong with printing title'
            quit()
        else:
            title = div.find_all('a',attrs={'class':'s-access-detail-page'})[0].get('title')
            title = unicode(title).encode('ascii','ignore')
        
        if div.find_all('a',attrs={'class':'s-access-detail-page'}) == []: print 'There is something wrong with itemlink' 
        else: itemlink = div.find_all('a',attrs={'class':'s-access-detail-page'})[0].get('href')
        

        if div.find_all('span',attrs={'class':'a-size-base a-color-price a-text-bold'}) == []:
            ## This could be a wrong way to detect tradeinprice, check this later
            price = 0.001
        else:
            try: priceraw =  div.find_all('span',attrs={'class':'a-size-base a-color-price a-text-bold'})[0].contents[0]
            except: print "something wrong with printing price raw"
            price = float(re.findall('\$(.+)*',priceraw)[0].replace(',','').replace('$',''))

        try: isbn = div.get('data-asin')
        except:
            print 'isbn not properly read'
            sys.exit()
            
        tradeinpricebox =  div.find('div',attrs={'class':'a-column a-span5 a-span-last'})
        if tradeinpricebox.find('span',attrs={'class':'a-color-price'}) == None:
            ## This could be a wrong way to detect tradeinprice, check this later
            tradeinprice = 0
        else:
            try:
                tradeinpricebox = tradeinpricebox.find('div',attrs={'class':'a-row a-spacing-none'})
                tradeinprice = tradeinpricebox.find('span',attrs={'class':'a-color-price'}).contents[0]
                tradeinprice = float(re.findall('\$(.+)*',tradeinprice)[0].replace(',','').replace('$',''))
            except:
                print "No trade-in price detected"
                tradeinprice = 0
                print price , tradeinprice, isbn
                
            
        
        priceofferslink =  "https://www.amazon.com/gp/offer-listing/"+ str(isbn) +"/ref=olp_f_usedAcceptable?ie=UTF8&f_new=true&f_usedGood=true&f_usedLikeNew=true&f_usedVeryGood=true&overridePriceSuppression=1&sort=taxsip"
        
        ## If tradeinprice exists, we will try to save it to a file.
        ## This is shared between multiuple multiprocessing mtretretrelMake a list of odules
        if tradeinprice == 0: continue
        else: pass
        
        if tradeinprice > 10: sharedproxs[1].append(isbn)
        else: pass

        
        
        profit = tradeinprice - (price + 3.99)
        if profit > 10:
            count += 1
            print profit , price , tradeinprice, isbn
            print 'Checking if any items are profitable'
            print priceofferslink
            profitable_result = check_profitable(priceofferslink,sharedproxs[0], tradeinprice)
            if profitable_result == []: return []
            else: pass

            print 'There exist at least one profitable item, appending the item to data'
            titlehtml = '<a href="' + itemlink +'">' + title + '</a>'
            titlehtml= unicode(titlehtml).encode('ascii','ignore')
            isbncomparison = '<a href="http://www.bookfinder.com/buyback/search/#' + isbn + '">' + isbn + '</a>'
            isbncomparison = unicode(isbncomparison).encode('ascii','ignore')
            timestamp = datetime.datetime.now().strftime("%B %d %I:%M%p")
            ## If profitable percentage is less than 15%, skip.
            ## However the code fails to catch profit pargins that are for example 14% and prime (definately buyabke).
            ## Needs to correct this later.

            
            print [titlehtml + ' ' + isbncomparison + ' ' + timestamp, '-----' , '-----', '-----', '-----', '-----' , '-----' ]
            data.append([titlehtml + ' ' + isbncomparison + ' ' + timestamp, '-----' , '-----', '-----', '-----', '-----' , '-----' ])


            countsub = 0
            for lst in profitable_result:
                if lst == []: continue
                else:
                    count += 1
                    print lst
                    data.append(lst)
            if countsub == 0: print 'There was a difference in trade-in price, but no data has been added and printed'
            else: pass
        else: pass

    #If the price doesn't meet the profitability cutoff, 
    if count == 0:return []
    else:return data

    

if __name__ == '__main__':
    beginning = time.time()
    totalisbns = 0
    totisbnlst = []
    categorylst = filename_extractor('good_isbns/')
    print categorylst 
    get_proxy()

    index = 0
    for category in categorylst:
        index += 1 
        start = time.time()
        if index == 1: pass
        else: random_proxylst_choice()
        try:
            text_file = open('good_isbns/' + category+ '.txt','r')
            print category + '.txt opened'
            isbns = text_file.read()
            isbns = isbns.strip()
            isbnslst = isbns.split()
            text_file.close()
        except: continue

        if len(isbnslst) == 0: continue
        else: totalisbns += len(isbnslst)
        print 'Number of ISBNS to be processed: ',  len(isbnslst)
        
        isbnchunk = []
        isbn_inteval = 80
        for i in range(0,len(isbnslst),isbn_inteval):
            if i + isbn_inteval <= len(isbnslst): isbnchunk.append("%7C".join(isbnslst[i:i+isbn_inteval]))
            else: isbnchunk.append("%7C".join(isbnslst[i:len(isbnslst)]))
        
        urls = []
        for isbns in tqdm(isbnchunk):
            url = 'https://www.amazon.com/s/ref=sr_pg_' + str(1) + '?rh=n%3A283155%2Cp_66%3A' + isbns +'&page=' + str(1) + '&sort=relevanceexprank&unfiltered=1&ie=UTF8'
            urls.append(url)
            ##Needs to fix this 
            response = wait_for_internet_connection(url)
            soup = BeautifulSoup(response.content,'html.parser')
            if soup.find_all('span',attrs={'class':'pagnDisabled'}) == []:
                try:
                    lastpageraw = soup.find_all('span',attrs={'class':'pagnLink'})
                    lastpage = int(soup.find_all('span',attrs={'class':'pagnLink'})[len(lastpageraw)-1].string)
                except IndexError:
                    print 'Only one page is available'
                    lastpage = 1
            else:
                try: lastpage = int(soup.find_all('span',attrs={'class':'pagnDisabled'})[0].contents[0])
                except: print "There was something wrong with reading lastpage"
            
            for page in range(2,lastpage+1):
                url = 'https://www.amazon.com/s/ref=sr_pg_' + str(page) + '?rh=n%3A283155%2Cp_66%3A' + url[url.index('Cp_66%3A')+len('Cp_66%3A'):url.index('&page=')] +'&page=' + str(page) + '&sort=relevanceexprank&unfiltered=1&ie=UTF8'
                urls.append(url)

        print len(urls)
        proxs = get_proxy_saved()
        manager = Manager()
        freshproxies = manager.list(proxs)
        ##Stores trade-in prices that exists and greater than 0.
        profitableisbns = [] 
        manager2 = Manager()
        
        bbpriceisbns = manager2.list(profitableisbns)
        partial_fetch_url = partial(fetch_url,sharedproxs = (freshproxies,bbpriceisbns))
        
        p = Pool(4)
        result = p.map(partial_fetch_url,urls, chunksize = 1)
        p.close()
        p.join() 
        print 'Runtime: %ss' % (time.time()-start)
        print bbpriceisbns
        ## Saves any isbns that contained tradeinprice > 10
##        if bbpriceisbns == []: pass
##        else:
##            f = open( 'good_isbns/'+ category+'.txt','w')
##            f.write( ' '.join(bbpriceisbns) )
##            f.close()


        ## There is a high chance that none of 200 isbns are even good. Fix how I entere and scrape isbns.
        refined_result = []
        for sublist in result:
            if sublist == []: continue
            else:
                for profitablelst in sublist:
                    if profitablelst == []: continue
                    else: refined_result.append(profitablelst)
                    
        if len(refined_result) == 0: continue
        else: pass

        for lst in refined_result:
            totisbnlst.append(lst)
            
        # Creates pandata dataframe using the headers below, max_colwidth sets column with to maximum.
        # escape = False, allow html encoding
        df = pd.DataFrame(refined_result, columns=['URL','Buy','Sell','Profit','ROI','Comparison','TimeStamp'])
        pd.set_option('display.max_colwidth', -1)
        df.to_html('isbn_amazon/' +category +'.html',escape=False, index=False)
        
    df = pd.DataFrame(totisbnlst, columns=['URL','Buy','Sell','Profit','ROI','Comparison','TimeStamp'])
    pd.set_option('display.max_colwidth', -1)
    df.to_html('isbn_amazon/amazonprofit.html',escape=False, index=False)
    
    print 'Total Runtime: %ss' % (time.time()- beginning) 
    print 'Number of isbns read:', totalisbns
    print 'Number of ISBNs read per second:', totalisbns/(time.time()- beginning) 





