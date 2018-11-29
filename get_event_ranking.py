import datetime
import time
import re
import pytz
from bs4 import BeautifulSoup
import requests
import pandas as pd
import matplotlib.pyplot as plt


def request_ranking_info(url_top, force_if_event_inactive=False, time_interval=0.5):

    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
    # url_top = "https://www.showroom-live.com/event/kiwami_audition2"
    # base_url = "https://www.showroom-live.com"
    with requests.Session() as s:
        s.headers.update({'user-agent': user_agent})
        r = s.get(url_top)
    soup = BeautifulSoup(r.text, "lxml")

    if not check_event_status(soup):
        if not force_if_event_inactive:
            raise ValueError("開催中のイベントのurlが指定されていません")

    ul_ranking = soup.find(id="list-ranking")
    li_list = ul_ranking.find_all(class_="js-follow-li")

    info_list = []
    for li in li_list:
        d = {}
        d["room_name"] = li.find(class_="listcardinfo-main-text").text
        d["thumbnail_url"] = li.find_all("img")[0].attrs["data-src"]
        d["is_onlive"] = True if li.find(
            class_="label-room is-onlive") is not None else False
        d["rel_url_event_contrib"] = li.find(
            class_="room-ranking-link").attrs["href"]
        d["rel_url_profile"] = li.find(class_="profile-link").attrs["href"]
        d["rel_url_room"] = li.find(class_="room-url").attrs["href"]

        info_list.append(d)

    df = pd.DataFrame(info_list)
    df["room_id"] = df.rel_url_profile.str.extract(
        "room_id=(\d+)", expand=False)
    with requests.Session() as s:
        df["current_score"] = df.room_id.apply(
            get_current_score, time_interval=time_interval, session=s)
    df.current_score = pd.to_numeric(df.current_score)

    tz = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(tz).replace(second=0, microsecond=0, tzinfo=None)
    df["Date"] = now

    return df


def get_current_score(room_id, time_interval=0.5, session=None):
    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
    url_event = "https://www.showroom-live.com/room/event"
    regex_ptn_current_score = "現在の合計ポイント：\D*(\d+)pt"
    headers = {'user-agent': user_agent}
    if session:
        session.headers.update(headers)
        r = session.get(url_event, params={"room_id": room_id})
    else:
        r = requests.get(url_event, params={
                         "room_id": room_id}, headers=headers)

    soup = BeautifulSoup(r.text, "lxml")
    score_total = soup.find(class_="fs-b4 fcol-white fl-l")
    if score_total:
        score_total = score_total.text
    else:
        print("room_id ({}) のポイントを取得できません".format(room_id))
        return None
    m = re.search(regex_ptn_current_score, score_total)
    if m:
        current_score = m.groups()[0]
    else:
        print("ポイント表記の正規表現が不適切です")
        current_score = None
    time.sleep(time_interval)
    return current_score


def check_event_status(soup):
    if not soup.find(id="event-room-list"):
        print("イベントページのurlではありません")
        return False
    event_period = soup.find(class_="info").text
    m = re.search("(.+) - (.+)", event_period)

    tz = pytz.timezone('Asia/Tokyo')
    date_start, date_end = map(
        lambda x: pd.Timestamp(m.groups()[x], tz=tz), [0, 1])
    now = datetime.datetime.now(tz=tz)
    if date_start > now:
        print("開催前です")
        return False
    if date_end < now:
        print("イベントは終了しています")
        return False

    event_labels = soup.find_all(class_="head")
    if len(event_labels) == 0:
        print("イベントの種類を判別できません")
        return False
    for label in event_labels:
        if "Ranking" in label.text:
            return True
    print("イベントの種類がランキング型ではありません")
    return False


if __name__ == '__main__':
    df = request_ranking_info("https://www.showroom-live.com/event/ske48_9th_audition")
    df.sort_values("current_score", ascending=True).plot(x="room_name", y="current_score", kind="barh", legend=None, figsize=(8, 8))
    plt.xticks(rotation=20)
    plt.title('showroomランキング')
    _ = plt.xlabel("現在のポイント")
    _ = plt.ylabel("")
    plt.savefig("temp.png")
