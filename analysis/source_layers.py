"""Source-directory classification, not a certification of article authority.

Collection transport (for example the ``osint-`` prefix) does not identify a
publisher. Unknown sources stay unclassified until their identity is checked.
"""
from pathlib import PurePath

MINISTRY = {
    "osint-ndrc_news", "osint-mof_news", "osint-miit_news", "osint-pbc_news",
    "osint-cac_news", "osint-sasac_news", "osint-stats_nbs", "osint-csrc_news",
    "osint-mofcom_news", "osint-mfa_presser", "osint-nea_news", "osint-safe_news",
}
MEDIA = {
    "renmin-ribao", "guangming", "banyuetan", "liaowang", "jingjiwang",
    "huanqiu", "qiushi", "xuexi-shibao", "chao-news", "rss", "wechat",
    "thepaper-pinglun", "bjnews", "qiushi-english-edition",
    "osint-stcn_news", "osint-people_daily", "osint-gmw",
    "osint-economic_daily", "osint-21jingji_news", "osint-yicai_news",
}
ACADEMIC = {"_academic", "aisixiang", "osint-cass_news", "osint-drc_news"}
LOCAL = {"local-gov-leaders"}


def sublayer_of(src: str, path: str = "") -> str:
    if src == "_primary-sources" or "_primary-sources" in PurePath(path).parts:
        return "A0_中央文件"
    if src in MINISTRY:
        return "A1_部委发布"
    if src in MEDIA:
        return "B_主流媒体"
    if src in ACADEMIC:
        return "D_学术智库"
    if src == "local-papers":
        return "C1_地方党报"
    if src in LOCAL:
        return "C_地方实践"
    return "Z_其他"


def layer_of(src: str) -> str:
    sub = sublayer_of(src)
    return "A_官方发布" if sub.startswith("A") else sub
