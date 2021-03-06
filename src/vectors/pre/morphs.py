import csv
import math
import os
import pickle
import sys
from collections import defaultdict, OrderedDict
from itertools import combinations
from random import randint

import numpy as np
import pandas as pd
from bokeh.core.property.dataspec import value
from bokeh.io import show
from bokeh.io.export import export_svg, export_png
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    Label,
)
from bokeh.plotting import figure
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from sklearn.manifold import TSNE

from src.config.settings import DATA_DIR, OUTPUTS_DIR, BASE_DIR
from src.preprocessing.cluster import min_max_normalize, read_word_vector_docs

format_string = "{}. {}_result.csv"
options = Options()
options.add_argument("--headless")
MORPHS_PATH = os.path.join(DATA_DIR, "morphs")
KEYWORD_PATH = os.path.join(DATA_DIR, "keywords")

FUTURES_PATH = os.path.join(DATA_DIR, "futures")

csv.field_size_limit(sys.maxsize)


def standard(arr):
    data = np.array(arr)
    std_data = (data - np.mean(data, axis=0)) / np.std(data, axis=0)
    return std_data


def get_cluster_data():
    with open(os.path.join(OUTPUTS_DIR, "cluster-docs.csv")) as f:
        return list(csv.reader(f))[1:]


def get_data(path):
    ret = {}
    dirs = os.listdir(path)
    dirs.sort()
    for directory in dirs:
        detail_dir = os.listdir(os.path.join(path, directory))
        detail_dir.sort()
        for filename in detail_dir:
            name, ext = filename.split(".csv")
            df = pd.read_csv(
                os.path.join(path, directory, filename), header=0
            ).fillna(value="1")
            words = df["형태소"].to_list()
            try:
                weight = df["가중치"].to_list()
            except KeyError:
                weight = [1 for _ in range(len(words))]
            ret[name.split(".")[1].strip() if "." in name else name] = list(
                zip(words, weight)
            )

    # ret = {}
    # vectors = []
    # with open(os.path.join(FUTURES_PATH, "future_vector.csv")) as f:
    #     for vector in list(csv.reader(f))[1:]:
    #         merged = [f"{vector[0].strip()}: {v.strip()}" for v in vector]
    #         vectors += merged[1:]
    # files = os.listdir(path)
    # files = [
    #     file for file in files if all(["euckr" not in file, "공통" not in file])
    # ]
    # files.sort()
    # for idx, filename in enumerate(files):
    #     with open(os.path.join(path, filename)) as f:
    #         reader = list(csv.reader(f))[1:]
    #         ret[vectors[idx].strip()] = reader
    return ret


def get_raw_content():
    with open(
        os.path.join(OUTPUTS_DIR, "index-raw-papers.csv"), encoding="utf-8",
    ) as f:
        raw_data = list(csv.reader(f))
    return raw_data


def export_vectors(morphs, cluster_data):
    raw_data = get_raw_content()
    keys = list(morphs.keys())
    vector_header = []
    for i in range(0, len(keys), 2):
        vector_header.append(f"{keys[i]} | {keys[i + 1]}")
    header = ["index", "cate", "year", "title", "cluster", *vector_header]
    ret = [header]
    for item in cluster_data:
        idx, *remain, context, cluster, distance = item
        raw = raw_data[int(idx)][4]

        temp = []
        for key, value in morphs.items():
            total = 0.0
            keywords = set(item for item in value)
            for k, weight in keywords:
                if isinstance(weight, str):
                    weight = float(weight)
                c = raw.count(k)
                v = weight * c
                total += v
            temp.append(math.sqrt(math.sqrt(total)))

        merge = []

        for i in range(0, len(temp), 2):
            diff = temp[i + 1] - temp[i]

            merge.append(diff)
        ret.append([idx, *remain, cluster, *merge])
    with open(os.path.join(OUTPUTS_DIR, "future_vectors_raw.csv"), "w") as f:
        reader = csv.writer(f)
        reader.writerows(ret)


def export_vectors2(morphs, cluster_data):
    raw_data = get_raw_content()
    keys = list(morphs.keys())
    vector_header = []
    for i in range(0, len(keys), 2):
        vector_header.append(f"{keys[i]} | {keys[i + 1]}")
    header = ["index", "cate", "year", "title", "cluster", *vector_header]
    ret = [header]
    extra = [[] for _ in range(len(keys))]
    for item in cluster_data:
        idx, *remain, context, cluster, distance = item
        raw = raw_data[int(idx)][4]
        for i, r in enumerate(morphs.items()):
            key, value = r
            total = 0
            keywords = set(item for item in value)
            for k in keywords:
                total += raw.count(k)
            # v = math.sqrt(math.sqrt(total))
            extra[i].append(total)
    for i in range(len(extra)):
        extra[i] = min_max_normalize(extra[i])
    for item in cluster_data:
        idx, *remain, context, cluster, distance = item
        temp = []
        for i in range(0, len(keys), 2):
            v1 = extra[i][int(idx) - 1]
            v2 = extra[i + 1][int(idx) - 1]
            temp.append(v2 - v1)
        ret.append([idx, *remain, cluster, *temp])
    with open(
        os.path.join(OUTPUTS_DIR, "normalized_future_vectors.csv"), "w"
    ) as f:
        reader = csv.writer(f)
        reader.writerows(ret)


def export_normalized_future_vectors(is_divide=False):
    with open(os.path.join(OUTPUTS_DIR, "future_vectors_raw.csv")) as f:
        reader = list(csv.reader(f))
    ret = [[] for _ in range(len(reader[0]) - 5)]
    for row in reader[1:]:
        _, _, _, _, _, *count = row
        for idx, v in enumerate(count):
            ret[idx].append(float(v))
    normals = []
    if is_divide:
        for idx, r in enumerate(ret):
            df = pd.DataFrame({"value": r})
            positive = min_max_normalize(df.loc[df.value >= 0].value.to_list())
            negative = min_max_normalize(df.loc[df.value < 0].value.to_list())
            df.loc[df.value >= 0, "value"] = positive
            df.loc[df.value < 0, "value"] = [-1 + n for n in negative]

            normals.append(df.value.to_list())
    else:
        for r in ret:
            temp = min_max_normalize(r)
            normals.append([(t - 0.5) * 2 for t in temp])
    data = [reader[0]]
    for idx, row in enumerate(reader[1:]):
        temp = []
        for i in range(len(row) - 5):
            temp.append(normals[i][idx])
        data.append(row[:5] + temp)
    with open(
        os.path.join(OUTPUTS_DIR, "normalized_future_vectors.csv"), "w"
    ) as f:
        reader = csv.writer(f)
        reader.writerows(data)


def export_normalized_future_cluster_vectors(
    filename="normalized_future_vectors.csv",
):

    clusters = set()
    with open(os.path.join(OUTPUTS_DIR, filename)) as f:
        reader = list(csv.reader(f))
    for row in reader[1:]:
        clusters.add(row[4])
    clusters = list(clusters)
    clusters.sort()
    header = ["index", "미래벡터", *clusters]
    origin_header = reader[0]
    ret = [header]
    for i, idx in enumerate(range(5, len(origin_header))):
        temp = [i, origin_header[idx]]
        dic = defaultdict(list)
        for row in reader[1:]:
            dic[row[4]].append(float(row[idx]) * (int(row[2]) - 1994) / 26)
        for key in dic.keys():
            dic[key] = sum(dic[key]) / len(dic[key])
        for c in clusters:
            temp.append(dic[c])
        ret.append(temp)

    # ret.insert(0, ["cluster", *reader[0][5:]])
    with open(
        os.path.join(OUTPUTS_DIR, "normalized_future_cluster_vectors.csv"), "w"
    ) as f:
        w = csv.writer(f)
        w.writerows(ret)
    with open(
        os.path.join(
            OUTPUTS_DIR, "normalized_future_cluster_vectors_euckr.csv"
        ),
        "w",
        encoding="euc-kr",
    ) as f:
        w = csv.writer(f)
        w.writerows(ret)


def export_comb(morphs):
    ret = []
    keys = list(morphs.keys())
    for i in range(0, len(keys), 2):
        ret.append(f"{keys[i]} | {keys[i + 1]}")
    comb = list(combinations(ret, 2))
    with open(os.path.join(OUTPUTS_DIR, "future_comb.csv"), "w") as f:
        w = csv.writer(f)
        w.writerows([("가로축", "세로축"), *enumerate(comb, 1)])
    with open(
        os.path.join(OUTPUTS_DIR, "future_comb_euckr.csv"),
        "w",
        encoding="euc-kr",
    ) as f:
        w = csv.writer(f)
        w.writerows([("가로축", "세로축"), *enumerate(comb, 1)])


def draw_vectors():
    driver = webdriver.Chrome(
        os.path.join(BASE_DIR, "chromedriver"), options=options
    )

    df = pd.read_csv(
        os.path.join(OUTPUTS_DIR, "normalized_future_vectors.csv")
    )
    filter_list = {
        (5, 6),
        (5, 7),
        (6, 7),
        (8, 9),
        (8, 10),
        (9, 10),
        (11, 12),
        (11, 13),
        (12, 13),
    }
    comb = list(combinations(range(5, len(df.columns)), 2))
    comb = [c for c in comb if c not in filter_list]
    for idx, coord in enumerate(comb, 1):
        x, y = coord
        X = df[df.columns[x]].to_list()
        Y = df[df.columns[y]].to_list()
        tsne_df = pd.DataFrame(
            zip(X, Y), index=range(len(X)), columns=["x_coord", "y_coord"]
        )
        tsne_df["title"] = df["title"].to_list()
        tsne_df["cluster_no"] = df["cluster"].to_list()
        colormap = {3: "#ffee33", 2: "#00a152", 1: "#2979ff", 0: "#d500f9"}
        # colormap = {3: "#bdbdbd", 2: "#bdbdbd", 1: "#bdbdbd", 0: "#d500f9"}
        # colormap = {3: "#bdbdbd", 2: "#bdbdbd", 1: "#2979ff", 0: "#bdbdbd"}
        # colormap = {3: "#bdbdbd", 2: "#00a152", 1: "#bdbdbd", 0: "#bdbdbd"}
        # colormap = {3: "#ffee33", 2: "#bdbdbd", 1: "#bdbdbd", 0: "#bdbdbd"}
        only_one_cluster = pd.DataFrame(tsne_df.loc[tsne_df.cluster_no == 3])
        colors = [colormap[x] for x in only_one_cluster["cluster_no"]]

        only_one_cluster["color"] = colors
        plot_data = ColumnDataSource(
            data=only_one_cluster.to_dict(orient="list")
        )
        plot = figure(
            # title='TSNE Twitter BIO Embeddings',
            plot_width=1600,
            plot_height=1600,
            active_scroll="wheel_zoom",
            output_backend="svg",
            x_range=(-1.1, 1.1),
            y_range=(-1.1, 1.1),
        )
        plot.add_tools(HoverTool(tooltips="@title"))
        plot.circle(
            source=plot_data,
            x="x_coord",
            y="y_coord",
            line_alpha=0.6,
            fill_alpha=0.6,
            size=20,
            fill_color="color",
            line_color="color",
        )
        plot.yaxis.axis_label_text_font_size = "25pt"
        plot.yaxis.major_label_text_font_size = "25pt"
        plot.xaxis.axis_label_text_font_size = "25pt"
        plot.xaxis.major_label_text_font_size = "25pt"
        start_x, end_x = df.columns[x].split("|")
        start_y, end_y = df.columns[y].split("|")
        start_x = start_x.strip()
        end_x = end_x.strip()
        start_y = start_y.strip()
        end_y = end_y.strip()
        plot.title.text_font_size = value("32pt")
        plot.xaxis.visible = True
        # plot.xaxis.bounds = (0, 0)
        plot.yaxis.visible = True
        label_opts1 = dict(x_offset=0, y_offset=750, text_font_size="30px",)
        msg1 = end_y
        caption1 = Label(text=msg1, **label_opts1)
        label_opts2 = dict(x_offset=0, y_offset=-750, text_font_size="30px",)
        msg2 = start_y
        caption2 = Label(text=msg2, **label_opts2)
        label_opts3 = dict(x_offset=600, y_offset=0, text_font_size="30px",)
        msg3 = end_x
        caption3 = Label(text=msg3, **label_opts3)
        label_opts4 = dict(x_offset=-750, y_offset=0, text_font_size="30px",)
        msg4 = start_x
        caption4 = Label(text=msg4, **label_opts4)
        plot.add_layout(caption1, "center")
        plot.add_layout(caption2, "center")
        plot.add_layout(caption3, "center")
        plot.add_layout(caption4, "center")
        plot.background_fill_color = None
        plot.border_fill_color = None
        plot.grid.grid_line_color = None
        plot.outline_line_color = None
        plot.yaxis.fixed_location = 0
        plot.xaxis.fixed_location = 0
        plot.toolbar.logo = None
        plot.toolbar_location = None
        print(idx)
        export_svg(
            plot,
            filename=f"svgs/{idx}.svg",
            webdriver=driver,
            height=1600,
            width=1600,
        )
        export_png(
            plot,
            filename=f"pngs/{idx}.png",
            webdriver=driver,
            height=1600,
            width=1600,
        )
        # show(plot)


def export_distance_from_cluster(cluster_data):
    with open(os.path.join(OUTPUTS_DIR, "network-detail-draw.csv")) as f:
        network = list(csv.reader(f))
    with open(os.path.join(OUTPUTS_DIR, "normalized_future_vectors.csv")) as f:
        docs = list(csv.reader(f))
    with open(
        os.path.join(OUTPUTS_DIR, "normalized_future_cluster_vectors.csv")
    ) as f:
        clusters = list(csv.reader(f))
    header = docs[0] + ["connected_node_count", "distance_from_cluster"]
    ret = [header]
    cluster_map = OrderedDict()
    _, _, *cs = clusters[0]
    for c in cs:
        cluster_map[c] = []
        # _, *cs = k
    keys = list(cluster_map.keys())
    # print(cluster_map)
    for row in clusters[1:]:
        _, _, *idxs = row
        for idx, value in enumerate(idxs):
            cluster_map[keys[idx]].append(value)
    for row in docs[1:]:
        index, cate, year, title, cluster, *vs = row
        ret.append(
            [
                index,
                cate,
                year,
                title,
                cluster,
                *vs,
                network[int(index)][3],
                cluster_data[int(index) - 1][6],
            ]
        )
    with open(
        os.path.join(
            OUTPUTS_DIR,
            "normalized_future_vectors_with_distance_from_cluster.csv",
        ),
        "w",
    ) as f:
        w = csv.writer(f)
        w.writerows(ret)


def main():
    # morphs = get_data(KEYWORD_PATH)
    # clusters = get_cluster_data()
    # export_vectors(morphs, clusters)
    # export_vectors2(morphs, clusters)  # normalize 포함
    # export_normalized_future_vectors(is_divide=True)
    # export_normalized_future_cluster_vectors()
    # export_distance_from_cluster(clusters)
    # export_comb(morphs)
    draw_vectors()


if __name__ == "__main__":
    main()
