import requests
from requests.exceptions import Timeout
import pandas as pd
import json
import os
import time
import datetime
from datetime import timedelta
import numpy as np
import timeseries as ts
import app_config as cfg
import paho.mqtt.client as paho
import grequests
config = cfg.getconfig()

class dataEx:
    def __init__(self):
        self.url_kairos = config['api']['query']
        self.post_url = config["api"]["datapoints"] 
        self.now = int(time.time()*1000) 
        
        
    def getTagmeta(self,unitsId):
        query = {"unitsId":unitsId}
        url = config["api"]["meta"] + '/tagmeta?filter={"where":' + json.dumps(query) + '}'
        response = requests.get(url,headers={"Authorization": self.token})
        if(response.status_code==200):
            # print(response.status_code)
            # print("Got tagmeta successfully.....")
            tagmeta = json.loads(response.content)
            df = pd.DataFrame(tagmeta)
        else:
            print("error in fetching tagmeta")
            df = pd.DataFrame()
        return df
        
        
    def getLoginToken(self):
        url = "https://pulse.thermaxglobal.com/exactapi/Users/login"
        res= requests.post(url,json={"email":"rohit.r@exactspace.co","password":"Thermax@123","ttl":0})
        res = json.loads(res.content)
        self.token =  res["id"]
        
    def get5MinValues(self,tagList):
        d = {
      "metrics": [
        {
          "tags": {},
          "name": ""
        }
      ],
      "plugins": [],
      "cache_time": 0,
      "start_relative": {
        "value": "300",
        "unit": "seconds"
      }
    }
        for tag in tagList:
            d['metrics'][0]['name'] = tag
        # print(d)
        res=requests.post(url=self.url_kairos, headers={"Authorization": self.token}, json=d)
        values=json.loads(res.content)
        temp=0
        for val in values['queries']:
            try:
                df1=pd.DataFrame(val['results'][0]['values'], columns=['Time', val['results'][0]['name']])
                if temp==1:
                    df=pd.merge(df,df1, on='Time', how="outer")
                else:
                    df=df1 
            except Exception as e:
                print(e)
            temp=1

        df=df.drop_duplicates(keep='first').reset_index(drop=True)
        df['Date']=pd.to_datetime(df['Time'],unit='ms')
        return df
        
    def getValues(self,tagList,startTime,endTime):
        d = {
      "metrics": [
        {
          "tags": {},
          "name": "",
          "limit": "9",
          "order" :"desc"
        }
      ],
      "plugins": [],
      "cache_time": 0,
      "start_absolute": startTime,
      "end_absolute": endTime
    }
        for tag in tagList:
            d['metrics'][0]['name'] = tag
        # print(d)
        res=requests.post(url=self.url_kairos, headers={"Authorization": self.token}, json=d)
        values=json.loads(res.content)
        temp=0
        for val in values['queries']:
            try:
                df1=pd.DataFrame(val['results'][0]['values'], columns=['Time', val['results'][0]['name']])
                if temp==1:
                    df=pd.merge(df,df1, on='Time', how="outer")
                else:
                    df=df1 
            except Exception as e:
                print(e)
            temp=1

        df=df.drop_duplicates(keep='first').reset_index(drop=True)
        df['Date']=pd.to_datetime(df['Time'],unit='ms')
        return df
        
    def getLastValues(self,taglist,end_absolute=0):
        if end_absolute !=0:
            query = {"metrics": [],"start_absolute": 1, end_absolute: end_absolute}
        else:
            query = {"metrics": [],"start_absolute":1}
        for tag in taglist:
            query["metrics"].append({"name": tag,"order":"desc","limit":1})
        try:
            res = requests.post(self.url_kairos,json=query).json()
            df = pd.DataFrame([{"time":res["queries"][0]["results"][0]["values"][0][0]}])
            for tag in res["queries"]:
                try:
                    if df.iloc[0,0] <  tag["results"][0]["values"][0][0]:
                        df.iloc[0,0] =  tag["results"][0]["values"][0][0]
                    df.loc[0,tag["results"][0]["name"]] = tag["results"][0]["values"][0][1]
                except:
                    pass
        
        except Exception as e:
            print(e)
            return pd.DataFrame()
        return df
        
    def getValuesV2(self,tagList,startTime, endTime):
        url = config["api"]["query"]
        metrics = []
        for tag in tagList:
            tagDict = {
                  "tags": {},
                  "name": tag,
                  "aggregators": [
                    {
                      "name": "avg",
                      "sampling": {
                        "value": "1",
                        "unit": "minutes"
                      },
                      "align_end_time": True
                    }
                  ]
                }
            metrics.append(tagDict)
            
        query ={
            "metrics":metrics,
            "plugins": [],
            "cache_time": 0,
            "start_absolute": startTime,
            "end_absolute": endTime
            
        }
    #     print(json.dumps(query,indent=4))
        res=requests.post(url=url, json=query)
        values=json.loads(res.content)
        finalDF = pd.DataFrame()
        for i in values["queries"]:
    #         print(json.dumps(i["results"][0]["name"],indent=4))
            df = pd.DataFrame(i["results"][0]["values"],columns=["time",i["results"][0]["name"]])
    #         display(df)
    #         print("-"*100)
            try:
                finalDF = pd.concat([finalDF,df.set_index("time")],axis=1)
            except Exception as e:
                print(e)
                finalDF = pd.concat([finalDF,df],axis=1)
            
        finalDF.reset_index(inplace=True)
        return finalDF
        
    def dataExachangeCooling(self,taglist):
        df = self.get5MinValues(taglist)
        if len(df) > 0 and df[taglist[0]].mean() >0:
            print "HERE"
            df.dropna(inplace=True)
            df = df[df[taglist[0]]!='NaN']
            df.reset_index(drop=True,inplace=True)
            new_tag = taglist[0].replace('TJY','TTE')
            print(new_tag)
            # print(df)
            post_array = []
            for i in range(0,len(df)):
                if df.loc[i,taglist[0]] != None:
                    post = [int(df.loc[i,'Time']),float(df.loc[i,taglist[0]])]
                    post_array.append(post)
            # print(len(df),len(post_array))
            post_body = [{"name":new_tag,"datapoints":post_array,"tags": {"type":"derived"}}]
            res1 = requests.post(self.post_url,json=post_body)
            # print(post_body)
            print('*******************',res1.status_code,new_tag,'******************************')
            # print(df)
        else:
            df_LV = self.getLastValues(taglist)
            # print(df_LV)
            if len(df_LV) > 0 and df_LV.loc[0,taglist[0]] > 0:
                # print(self.now)
                endTime = df_LV.loc[0,'time']
                startTime = endTime - 1*1000*60*20
                df = self.getValues(taglist,startTime,endTime)
                df.dropna(inplace=True)
                df = df[df[taglist[0]]!='NaN']
                df.reset_index(drop=True,inplace=True)

                for i in range(0,len(df)):
                    df.loc[i,'Time'] = self.now - i * 1000*60
                    
                df['Date']=pd.to_datetime(df['Time'],unit='ms')
                new_tag = taglist[0].replace('TJY','TTE')
            
                print(new_tag)
                    # print(df)
                post_array = []
                for i in range(0,len(df)):
                    if df.loc[i,taglist[0]] != None:
                        try:
                            post = [int(df.loc[i,'Time']),float(df.loc[i,taglist[0]])]
                            post_array.append(post)
                        except:
                            post = [int(df.loc[i,'Time']),float(0)]
                            post_array.append(post)
                            
                # print(len(df),len(post_array))
                post_body = [{"name":new_tag,"datapoints":post_array,"tags": {"type":"derived"}}]
                res1 = requests.post(self.post_url,json=post_body)
                # print(post_body)
                print('*******************',res1.status_code,new_tag,'******************************')
                # print(df)
            else:
                # print(self.now)
                endTime = 1659466200000
                startTime = 1659465000000
                df = self.getValues(taglist,startTime,endTime)
                # print(df)
                df.dropna(inplace=True)
                df = df[df[taglist[0]]!='NaN']
                df.reset_index(drop=True,inplace=True)

                for i in range(0,len(df)):
                    df.loc[i,'Time'] = self.now - i * 1000*60
                    
                df['Date']=pd.to_datetime(df['Time'],unit='ms')
                new_tag = taglist[0].replace('CEN1','DUN')
                
                print(new_tag)
                # print(df)
                post_array = []
                for i in range(0,len(df)):
                    if df.loc[i,taglist[0]] != None:
                        post = [int(df.loc[i,'Time']),float(df.loc[i,taglist[0]])]
                        post_array.append(post)
                # print(len(df),len(post_array))
                post_body = [{"name":new_tag,"datapoints":post_array,"tags": {"type":"derived"}}]
                res1 = requests.post(self.post_url,json=post_body)
                # print(post_body)
                print('*******************',res1.status_code,new_tag,'******************************')
                # print(df)
                
    def dataExachangeChemicals(self,taglist,validDay,currentHour,currentMinute,last5Minute,currentTimeStamp):
    #Get the valid Data
        try:
            df = pd.read_csv(taglist[0]+".csv")
            df.dropna(axis=0,inplace=True)
            if len(df) >0:
                new_tag = taglist[0].replace("QBX1_","SMR_")
                # print(new_tag)
                df['Date']=pd.to_datetime(df['Time'],unit='ms',errors='coerce')
                
                # print(df)
                # print(df["Date"].isnull().sum())
                
                #creating upper and lower limits
                # Q1 = df[taglist[0]].quantile(0.25)
                # Q3 = df[taglist[0]].quantile(0.75)
                # IQR = Q3 - Q1
                # Upper_limit = Q3 + 3*IQR
                # Lower_limit = Q1 - 1.5*IQR
                # print(Lower_limit,Upper_limit)
                
                
                
                df['Day'] = df['Date'].dt.day
                df['Hour'] = df['Date'].dt.hour
                df['Minute'] = df['Date'].dt.minute

                
                valid_df = df[(df["Day"] == validDay) & (df["Hour"] == currentHour)
                        & (df["Minute"] <= currentMinute) & (df["Minute"] >= last5Minute) ].copy()
               
                if len(valid_df) == 0:
                    valid_df = df[:5]
                # print(df)
                # print(valid_df)
                
                valid_df.sort_values(by="Time",inplace=True,ascending=False)
                valid_df.reset_index(drop = True,inplace=True)
                
                for i in valid_df.index:
                    valid_df.loc[i,'newTime'] = currentTimeStamp - i*1000*60


                valid_df['newDate']=pd.to_datetime(valid_df['newTime'],unit='ms')
                
                # print(valid_df)
                post_url = config["api"]["datapoints"]
                post_array = []
                for i in range(0,len(valid_df)):
                    if valid_df.loc[i,taglist[0]] != None:
                        post = [int(valid_df.loc[i,'newTime']),float(valid_df.loc[i,taglist[0]])]
                        post_array.append(post)
                        
                post_body = [{"name":new_tag,"datapoints":post_array,"tags": {"type":"derived"}}]
                res1 = requests.post(post_url,json=post_body)
                # print(post_body)
                print("`"*30,str(res1.status_code),"`"*30)
        except Exception as e:
            print(e)
            pass
            
            
    def dataexHeating(self,miniList,startTime,endTime,noTag=False):
        if not noTag:
            maindf = self.getValuesV2(miniList,startTime,endTime)
        if noTag:
            maindf = self.getValuesV2(miniList,1646092800000,1646093100000)
        for tag in miniList:
            df = maindf[["time",tag]]
            df.dropna(how="any",inplace=True)
            # print(df)
            new_tag = tag.replace("CEN1","DUN")
            df.sort_values(by=["time"],inplace=True,ascending=False)
            df.reset_index(inplace=True,drop=True)
            
            # df['Date']=pd.to_datetime(df['time'],unit='ms',errors='coerce')
            if len(df) == 0 and not noTag:
                self.noDataTags.append(tag)
            elif len(df)!= 0:
                df.sort_values(by=["time"],inplace=True,ascending=False)
                df.reset_index(inplace=True,drop=True)
                for i in df.index:
                    df.loc[i,'newTime'] = self.now - i*1000*60
                df['newDate']=pd.to_datetime(df['newTime'],unit='ms')
                    
                post_url = config["api"]["datapoints"]
                post_array = []
                for i in range(0,len(df)):
                    if df.loc[i,tag] != None:
                        post = [int(df.loc[i,'newTime']),float(df.loc[i,tag])]
                        post_array.append(post)
                        
                post_body = [{"name":new_tag,"datapoints":post_array,"tags": {"type":"derived"}}]
                # print(post_body)
                try:
                    res1 = requests.post(post_url,json=post_body)
                    print("`"*30,str(res1.status_code),"`"*30)
                except:
                    pass
                # print(post_body)
                
            
            
    def dataExachangeHeating(self,tagList,startTime,endTime):
        stepSize = 20
        self.noDataTags = []
        for ss in range(0,len(tagList),stepSize):
            miniList = tagList[ss:ss+stepSize]
            self.dataexHeating(miniList,startTime,endTime)
            
        for ss in range(0,len(self.noDataTags),stepSize):
            miniList = self.noDataTags[ss:ss+stepSize]
            self.dataexHeating(miniList,startTime,endTime,True)
            
            
    def downloadingFileMultipleFiles(self, fileNames):
        urls = []
        for file in fileNames:
            url = url = config['api']['meta']+"/attachments/reports/download/" +  file
            urls.append(url)
            # print(url)
            
        rs = (grequests.get(u) for u in urls)
        requests = grequests.map(rs)
        
        for i in range(len(requests)):
            if(requests[i].status_code==200):
                open(""+fileNames[i], "wb").write(requests[i].content)
                print("Downloading completed for file " + str(fileNames[i]))
            else:
                print(requests[i].status_code)
                print(requests[i].content)
            
    def removeFiles(self,fileNames):
        for file in fileNames:
            try:
                os.remove(file)
            except:
                pass