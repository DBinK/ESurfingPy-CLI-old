"""
GitHub: https://github.com/Aixzk/ESurfingPy
"""

import re
import RSA
import OCR
import time
import json
import requests

# 带时间前缀输出
printWithTime = lambda log: print(time.strftime('[%Y-%m-%d %H:%M:%S]', time.localtime()), log)

def login(esrfingurl, wlanacip, wlanuserip, account, password, details, debug):
    """发送 GET 请求登录校园网"""

    showDetail = lambda text: printWithTime(text) if details else None
    showDebug = lambda text: printWithTime('[debug] ' + text) if debug else None

    logData = {
        'time': time.time(),  # 开始时间
        'times': 0  # 验证码识别错误次数（不符合条件的不算）
    }

    while True:
        # 获取 JSESSIONID
        try:
            url = 'http://{}/qs/index_gz.jsp?wlanacip={}&wlanuserip={}'.format(esrfingurl, wlanacip, wlanuserip)
            showDetail('正在获取 JSESSIONID ...')
            showDebug('发送 GET 请求：{}'.format(url))
            getResponse = requests.get(url)
            showDebug('收到 GET 回应：{}\ncookies: {}\ncontent: {}'.format(getResponse, getResponse.cookies, getResponse.content.decode()))
            JSESSIONID = getResponse.cookies['JSESSIONID']
            showDetail('成功获取 JSESSIONID')
            showDebug('成功获取 JSESSIONID: {}'.format(JSESSIONID))
        except Exception as Exc:
            printWithTime('获取 JSESSIONID 时发生错误：\n{}'.format(Exc))
            returnData = {
                'result': 'failed',
                'locate': 'JSESSIONID',
                'reason': Exc
            }
            return returnData

        # 获取并识别验证码
        while True:
            # 保存验证码
            try:
                showDetail('正在获取验证码...')
                verifyCodeRegex = re.search('/common/image_code\.jsp\?time=\d+', str(getResponse.content)).group()
                verifyCodeURL = 'http://{}{}'.format(esrfingurl, verifyCodeRegex)
                showDebug('验证码网址: {}'.format(verifyCodeURL))
                headers = {
                    'Cookie': 'JSESSIONID=' + JSESSIONID,
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
                }
                showDebug('发送 Get 请求获取验证码')
                verifyCode = requests.get(url=verifyCodeURL, headers=headers)
                with open('Code.jpg', 'wb') as vcodeFile:  # 保存到 Code.jpg
                    vcodeFile.write(verifyCode.content)
                    showDebug('已保存到运行目录下的 Code.jpg')
                showDetail('成功获取验证码')
            except Exception as Exc:
                printWithTime('获取验证码时发生错误：\n{}'.format(Exc))
                returnData = {
                    'result': 'failed',
                    'locate': 'GetVerifyCode',
                    'reason': Exc
                }
                return returnData

            # 识别验证码
            try:
                tempTime = time.time()
                showDetail('正在识别验证码...')
                showDebug('调用 Tesseract 识别验证码')
                verifyCodeResult = OCR.imageOCR('Code.jpg')[0:4]  # 只取前4位
                timeTaken = round(time.time() - tempTime, 2)
                showDetail('识别验证码结果：{} 耗时：{}s'.format(verifyCodeResult, timeTaken))
                showDebug('识别验证码结果：{} 耗时：{}s'.format(verifyCodeResult, timeTaken))
                if len(verifyCodeResult) == 4:  # 验证码识别结果不是 4 位
                    break
                else:
                    showDetail('识别结果不符合条件')
                    showDebug('识别结果不符合条件')
                    continue
            except Exception as Exc:
                printWithTime('识别验证码时发生错误：\n{}'.format(Exc))
                returnData = {
                    'result': 'failed',
                    'locate': 'OCRVerifyCode',
                    'reason': Exc
                }
                return returnData

        # 计算 loginKey
        try:
            tempTime = time.time()
            showDetail('正在计算 loginKey ...')
            showDebug('执行 RSA JavaScript 计算 loginKey ...')
            loginKey = RSA.Encrypt(account, password, verifyCodeResult)
            timeTaken = round(time.time() - tempTime, 2)
            showDetail('完成计算，耗时：{}s'.format(timeTaken))
            showDebug('完成计算，耗时：{}s，loginKey：{}'.format(timeTaken, loginKey))
        except Exception as Exc:
            printWithTime('计算 loginKey 时发生错误：\n{}'.format(Exc))
            returnData = {
                'result': 'failed',
                'locate': 'loginKey',
                'reason': Exc
            }
            return returnData

        # 登录
        try:
            loginURL = 'http://{}/ajax/login'.format(esrfingurl)
            headers = {
                'Cookie': 'loginUser={}; JSESSIONID={}'.format(account, JSESSIONID),
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            }
            data = 'loginKey=' + loginKey + '&wlanuserip=' + wlanuserip + '&wlanacip=' + wlanacip
            showDetail('发送登录请求...')
            showDebug('发送 POST 请求：{}\nheaders: {}\ndata: {}'.format(loginURL, headers, data))
            postResponse = requests.post(url=loginURL, headers=headers, data=data)
            showDebug('收到 POST 回应：{}\ncookies: {}\ncontent: {}'.format(postResponse, postResponse.cookies, postResponse.content))
        except Exception as Exc:
            printWithTime('发送登录请求失败，原因：\n{}'.format(Exc))
            returnData = {
                'result': 'failed',
                'failed': 'Send login request',
                'reason': Exc
            }
            return returnData

        # 判断结果
        resultCode = json.loads(postResponse.text)['resultCode']
        resultInfo = json.loads(postResponse.text)['resultInfo']
        if resultCode == '0':  # 登录成功
            timeTaken = round(time.time() - logData['time'], 2)
            showDetail('登录成功，总耗时 {}s，失败 {} 次'.format(timeTaken, logData['times']))
            printWithTime('登陆成功, signature: {}'.format(postResponse.cookies['signature']))
            returnData = {
                'result': 'succeed',
                'signature': postResponse.cookies['signature']
            }
            return returnData
        elif resultCode == '13002000':  # 重复登录
            # resultInfo: '登录已经成功，请不要重复登录'
            timeTaken = round(time.time() - logData['time'], 2)
            showDetail('重复登录，总耗时 {}s，失败 {} 次'.format(timeTaken, logData['times']))
            printWithTime('登陆成功, signature: {}'.format(postResponse.cookies['signature']))
            returnData = {
                'result': 'succeed',
                'signature': postResponse.cookies['signature']
            }
            return returnData
        elif resultCode == '11063000':  # 验证码错误
            showDetail(resultInfo)
            logData['times'] += 1
            continue
        elif resultCode == '13005000':  # 请求认证超时
            showDetail(resultInfo)
            logData['times'] += 1
            continue
        elif resultCode == '13018000':  # 禁止网页认证
            # resultInfo: '已办理一人一号多终端业务的用户，请使用客户端登录'
            printWithTime(resultInfo)
            returnData = {
                'result': 'failed',
                'reason': resultInfo
            }
            return returnData
        else:  # 其他情况
            printWithTime('登陆失败，resultCode：{}  resultInfo：{}'.format(resultCode, resultInfo))
            returnData = {
                'result': 'failed',
                'reason': resultInfo
            }
            return returnData


def logout(esrfingurl, wlanacip, wlanuserip, account, signature, details, debug):
    """发送 POST 请求登出校园网"""

    showDetail = lambda text: printWithTime(text) if details else None
    showDebug = lambda text: printWithTime(text) if debug else None

    try:
        logTime = time.time()
        showDetail('正在登出 ...')
        url = 'http://{}/ajax/logout'.format(esrfingurl)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.87 Safari/537.36 SE 2.X MetaSr 1.0',
            'Cookie': 'signature={}; loginUser={}'.format(signature, account),
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        data = 'wlanuserip=' + wlanuserip + '&wlanacip=' + wlanacip
        showDebug('发送 POST 请求：{}\nheaders: {}\ndata: {}'.format(url, json.dumps(headers, indent=4), data))
        postResponse = requests.post(url=url, headers=headers, data=data)
        showDebug('收到 POST 回应：{}\nheaders: {}\ndata: {}'.format(postResponse, postResponse.headers, postResponse.content.decode()))
    except Exception as Exc:
        printWithTime('发送 POST 请求时发生错误：\n{}'.format(Exc))
        returnData = {
            'result': 'failed',
            'failed': 'POST',
            'reason': Exc
        }
        return returnData

    resultCode = json.loads(postResponse.text)['resultCode']
    resultInfo = json.loads(postResponse.text)['resultInfo']
    if resultCode == '0':  # 登出成功（或重复登出）
        timeTaken = round(time.time() - logTime, 2)
        showDetail('登出成功，耗时 {}s'.format(timeTaken))
        showDebug('登出成功，耗时 {}s'.format(timeTaken))
        returnData = {
            'result': 'succeed'
        }
    else:
        printWithTime('登出失败，返回状态码：{} 信息：{}'.format(resultCode, resultInfo))
        returnData = {
            'result': 'failed',
            'resultCode': resultCode,
            'resultInfo': resultInfo
        }
    return returnData