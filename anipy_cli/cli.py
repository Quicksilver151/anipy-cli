"""
Collection of 
all cli functions.
"""

import time
import os
import sys
from copy import deepcopy

from .mal import MAL
from .seasonal import Seasonal
from .url_handler import epHandler, videourl
from .history import history
from .misc import (
    error,
    entry,
    options,
    clear_console,
    print_names,
    seasonal_options,
    mal_options, search_in_season_on_gogo,
)
from .player import mpv, dc_presence_connect
from .query import query
from .arg_parser import parse_args
from .colors import colors
from .download import download
from .config import config

rpc_client = None
if config.dc_presence:
    rpc_client = dc_presence_connect()

mal = MAL()


def default_cli(quality):
    """
    Default cli(no flags like -H or -d)
    Just prints a search prompt and then
    does the default behavior.
    """
    show_entry = entry()
    query_class = query(input("Search: "), show_entry)
    if query_class.get_links() == 0:
        sys.exit()
    show_entry = query_class.pick_show()
    ep_class = epHandler(show_entry)
    show_entry = ep_class.pick_ep()
    url_class = videourl(show_entry, quality)
    url_class.stream_url()
    show_entry = url_class.get_entry()

    sub_proc = mpv(show_entry, rpc_client)
    menu(show_entry, options, sub_proc, quality).print_and_input()


def download_cli(quality, ffmpeg, no_season_search):
    """
    Cli function for the
    -d flag.
    """
    is_season_search = False
    print(colors.GREEN + "***Download Mode***" + colors.END)
    print(
        colors.GREEN
        + "Downloads are stored in: "
        + colors.END
        + str(config.download_folder_path)
    )

    show_entry = entry()
    searches = []
    show_entries = []
    if (
        not no_season_search
        and input("Search MyAnimeList for anime in Season? (y|n): \n>> ") == "y"
    ):
        searches = get_searches_from_gogo()

    else:
        another = "y"
        while another == "y":
            searches.append(input("Search: "))
            another = input("Add another search: (y|n)\n")

    for search in searches:
        links = 0
        query_class = None
        if isinstance(search, dict):
            is_season_search = True
            links = [search["category_url"]]

        else:
            print("\nCurrent: ", search)
            query_class = query(search, show_entry)
            query_class.get_pages()
            links = query_class.get_links()

        if links == 0:
            sys.exit()

        if is_season_search:
            show_entry = entry()
            show_entry.show_name = search["name"]
            show_entry.category_url = search["category_url"]

        else:
            show_entry = query_class.pick_show()

        ep_class = epHandler(show_entry)
        ep_list = ep_class.pick_range()
        show_entries.append(
            {"show_entry": deepcopy(show_entry), "ep_list": deepcopy(ep_list)}
        )

    for ent in show_entries:
        show_entry = ent["show_entry"]
        ep_list = ent["ep_list"]
        for i in ep_list:
            show_entry.ep = int(i)
            show_entry.embed_url = ""
            ep_class = epHandler(show_entry)
            show_entry = ep_class.gen_eplink()
            url_class = videourl(show_entry, quality)
            url_class.stream_url()
            show_entry = url_class.get_entry()
            download(show_entry, ffmpeg).download()


def history_cli(quality):
    """
    Cli function for the -H flag, prints all of the history,
    so user is able to pick one and continue watching.
    """
    show_entry = entry()
    hist_class = history(show_entry)

    json = hist_class.read_save_data()

    if not json:
        error("no history")
        return

    shows = [x for x in json]

    for num, val in enumerate(shows, 1):
        ep = json[val]["ep"]
        col = ""
        if num % 2:
            col = colors.YELLOW
        print(
            colors.GREEN
            + f"[{num}]"
            + colors.RED
            + f" EP: {ep}"
            + colors.END
            + f" |{col} {val}"
            + colors.END
        )

    while True:
        inp = input("Enter Number: " + colors.CYAN)
        try:
            if int(inp) <= 0:
                error("invalid input")
        except ValueError:
            error("invalid input")

        try:
            picked = shows[int(inp) - 1]
            break

        except:
            error("invalid Input")

    show_entry.show_name = picked
    show_entry.ep = json[picked]["ep"]
    show_entry.ep_url = json[picked]["ep-link"]
    show_entry.category_url = json[picked]["category-link"]
    show_entry.latest_ep = epHandler(show_entry).get_latest()
    url_class = videourl(show_entry, quality)
    url_class.stream_url()
    show_entry = url_class.get_entry()
    sub_proc = mpv(show_entry, rpc_client)
    menu(show_entry, options, sub_proc, quality).print_and_input()


def binge_cli(quality):
    """
    Cli function for the
    -b flag.
    """
    print(colors.GREEN + "***Binge Mode***" + colors.END)

    show_entry = entry()
    query_class = query(input("Search: "), show_entry)
    query_class.get_pages()
    if query_class.get_links() == 0:
        sys.exit()
    show_entry = query_class.pick_show()
    ep_class = epHandler(show_entry)
    ep_list = ep_class.pick_range()

    ep_urls = []
    for i in ep_list:
        ent = entry()
        ent.ep = int(i)
        ent.category_url = show_entry.category_url
        ep_class = epHandler(ent)
        ent = ep_class.gen_eplink()
        ep_urls.append(ent.ep_url)

    ep_list = {
        show_entry.show_name: {
            "ep_urls": ep_urls,
            "eps": ep_list,
            "category_url": show_entry.category_url,
        }
    }

    binge(ep_list, quality)


def seasonal_cli(quality, no_season_search, ffmpeg, auto_update):
    s = seasonalCli(quality, no_season_search, ffmpeg, auto_update)
    if auto_update:
        s.download_latest()

    else:
        s.print_opts()
        s.take_input()


class seasonalCli:
    def __init__(self, quality, no_season_search, ffmpeg=False, auto=False):
        self.entry = entry()
        self.quality = quality
        self.no_season_search = no_season_search
        self.s_class = Seasonal()
        self.ffmpeg = ffmpeg
        self.auto = auto

    def print_opts(self):
        for i in seasonal_options:
            print(i)

    def take_input(self):
        while True:
            picked = input(colors.END + "Enter option: ")
            if picked == "a":
                self.add_anime()
            elif picked == "e":
                self.del_anime()
            elif picked == "l":
                self.list_animes()
            elif picked == "d":
                self.download_latest()
            elif picked == "w":
                self.binge_latest()
            elif picked == "q":
                self.quit()
            else:
                error("invalid input")

    def add_anime(self):
        show_entry = entry()
        is_season_search = False
        searches = []
        if (
            not self.no_season_search
            and input("Search for anime in Season? (y|n): \n>> ") == "y"
        ):
            searches = get_searches_from_gogo()

        else:
            searches.append(input("Search: "))

        for search in searches:
            links = 0
            query_class = None
            if isinstance(search, dict):
                is_season_search = True
                links = [search["category_url"]]

            else:
                print("\nCurrent: ", search)
                query_class = query(search, show_entry)
                query_class.get_pages()
                links = query_class.get_links()

            if links == 0:
                sys.exit()

            if is_season_search:
                show_entry = entry()
                show_entry.show_name = search["name"]
                show_entry.category_url = search["category_url"]

            else:
                show_entry = query_class.pick_show()

            picked_ep = epHandler(show_entry).pick_ep_seasonal().ep
            Seasonal().add_show(
                show_entry.show_name, show_entry.category_url, picked_ep
            )
        clear_console()
        self.print_opts()

    def del_anime(self):
        seasonals = Seasonal().list_seasonals()
        seasonals = [x[0] for x in seasonals]
        print_names(seasonals)
        while True:
            inp = input("Enter Number: " + colors.CYAN)
            try:
                picked = seasonals[int(inp) - 1]
                break
            except:
                error("Invalid Input")

        Seasonal().del_show(picked)
        clear_console()
        self.print_opts()

    def list_animes(self):
        for i in Seasonal().list_seasonals():
            print(f"==> EP: {i[1]} | {i[0]}")

    def list_possible(self, latest_urls):
        for i in latest_urls:
            print(f"{colors.RED}{i}:")
            for j in latest_urls[i]["ep_list"]:
                print(f"{colors.CYAN}==> EP: {j[0]}")

    def download_latest(self):
        latest_urls = Seasonal().latest_eps()

        if not latest_urls:
            error("Nothing to download")
            return

        print("Stuff to be downloaded:")
        self.list_possible(latest_urls)
        if not self.auto:
            input(f"{colors.RED}Enter to continue or CTRL+C to abort.")

        for i in latest_urls:
            print(f"Downloading newest urls for {i}")
            show_entry = entry()
            show_entry.show_name = i
            for j in latest_urls[i]["ep_list"]:
                show_entry.embed_url = ""
                show_entry.ep = j[0]
                show_entry.ep_url = j[1]
                url_class = videourl(show_entry, self.quality)
                url_class.stream_url()
                show_entry = url_class.get_entry()
                download(show_entry, self.ffmpeg).download()

        if not self.auto:
            clear_console()
            self.print_opts()

        for i in latest_urls:
            Seasonal().update_show(i, latest_urls[i]["category_url"])

    def binge_latest(self):
        latest_eps = Seasonal().latest_eps()
        print("Stuff to be watched:")
        self.list_possible(latest_eps)
        input(f"{colors.RED}Enter to continue or CTRL+C to abort.")
        ep_list = []
        ep_urls = []
        ep_dic = {}
        for i in latest_eps:
            for j in latest_eps[i]["ep_list"]:
                ep_list.append(j[0])
                ep_urls.append(j[1])

            ep_dic.update(
                {
                    i: {
                        "ep_urls": [x for x in ep_urls],
                        "eps": [x for x in ep_list],
                        "category_url": latest_eps[i]["category_url"],
                    }
                }
            )
            ep_list.clear()
            ep_urls.clear()

        binge(ep_dic, self.quality, mode="seasonal")

        clear_console()
        self.print_opts()

    def quit(self):
        sys.exit(0)


class menu:
    """
    This is mainly a class for the cli
    interface, it should have a entry,
    with all fields filled. It also accepts
    a list of options that will be printed
    this is just a thing for flexebilyti.
    A sub_proc is also required this one is
    a subprocess instance returned by misc.mpv().
    """

    def __init__(self, entry, opts, sub_proc, quality) -> None:
        self.entry = entry
        self.options = opts
        self.sub_proc = sub_proc
        self.quality = quality

    def print_opts(self):
        for i in self.options:
            print(i)

    def print_status(self):
        clear_console()
        print(
            colors.GREEN
            + f"Playing: {self.entry.show_name} {self.entry.quality} | "
            + colors.RED
            + f"{self.entry.ep}/{self.entry.latest_ep}"
        )

    def print_and_input(self):
        self.print_status()
        self.print_opts()
        self.take_input()

    def kill_player(self):
        self.sub_proc.kill()

    def start_ep(self):
        self.entry.embed_url = ""
        url_class = videourl(self.entry, self.quality)
        url_class.stream_url()
        self.entry = url_class.get_entry()
        self.sub_proc = mpv(self.entry, rpc_client)

    def take_input(self):
        while True:
            picked = input(colors.END + "Enter option: ")
            if picked == "n":
                self.next_ep()
            elif picked == "p":
                self.prev_ep()
            elif picked == "r":
                self.repl_ep()
            elif picked == "s":
                self.selec_ep()
            elif picked == "h":
                self.hist()
            elif picked == "a":
                self.search()
            elif picked == "i":
                self.video_info()
            elif picked == "q":
                self.quit()
            else:
                error("invalid input")

    def next_ep(self):
        self.kill_player()
        ep_class = epHandler(self.entry)
        self.entry = ep_class.next_ep()
        self.print_status()
        self.start_ep()
        self.print_opts()

    def prev_ep(self):
        self.kill_player()
        ep_class = epHandler(self.entry)
        self.entry = ep_class.prev_ep()
        self.start_ep()
        self.print_status()
        self.print_opts()

    def repl_ep(self):
        self.kill_player()
        self.start_ep()

    def selec_ep(self):
        ep_class = epHandler(self.entry)
        self.entry = ep_class.pick_ep()
        self.kill_player()
        self.start_ep()
        self.print_status()
        self.print_opts()

    def hist(self):
        self.kill_player()
        history_cli(self.quality)

    def search(self):
        query_class = query(input("Search: "), self.entry)
        if query_class.get_links() == 0:
            return
        else:
            self.entry = query_class.pick_show()
            ep_class = epHandler(self.entry)
            self.entry = ep_class.pick_ep()
            self.kill_player()
            self.start_ep()
            self.print_status()
            self.print_opts()

    def video_info(self):
        print(f"Show Name: {self.entry.show_name}")
        print(f"Category Url: {self.entry.category_url}")
        print(f"Epiode Url: {self.entry.ep_url}")
        print(f"Episode: {self.entry.ep}")
        print(f"Embed Url: {self.entry.embed_url}")
        print(f"Stream Url: {self.entry.stream_url}")
        print(f"Quality: {self.entry.quality}")

    def quit(self):

        self.kill_player()
        sys.exit(0)


def binge(ep_list, quality, mode=""):
    """
    Accepts ep_list like so:
        {"name" {'ep_urls': [], 'eps': [], 'category_url': }, "next_anime"...}
    """
    print(f"{colors.RED}To quit press CTRL+C")
    try:
        for i in ep_list:
            show_entry = entry()
            show_entry.show_name = i
            show_entry.category_url = ep_list[i]["category_url"]
            show_entry.latest_ep = epHandler(show_entry).get_latest()
            for url, ep in zip(ep_list[i]["ep_urls"], ep_list[i]["eps"]):

                show_entry.ep = ep
                show_entry.embed_url = ""
                show_entry.ep_url = url
                print(
                    f"""{
                        colors.GREEN
                    }Fetching links for: {
                        colors.END
                    }{
                        show_entry.show_name
                    }{
                        colors.RED
                    } | EP: {
                        show_entry.ep
                    }/{
                        show_entry.latest_ep
                    }"""
                )
                url_class = videourl(show_entry, quality)
                url_class.stream_url()
                show_entry = url_class.get_entry()
                sub_proc = mpv(show_entry, rpc_client)
                while True:
                    poll = sub_proc.poll()
                    if poll is not None:
                        break
                    time.sleep(0.2)
                if mode == "seasonal":
                    Seasonal().update_show(
                        show_entry.show_name, show_entry.category_url
                    )
                elif mode == "mal":
                    mal.update_watched(show_entry.show_name, show_entry.ep)

    except KeyboardInterrupt:
        try:
            sub_proc.kill()
        except:
            pass
        sys.exit()

    return


def get_searches_from_gogo():
    searches = []
    selected = []
    season_year = None
    season_name = None
    while not season_year:
        try:
            season_year = int(input("Season Year: "))
        except ValueError:
            print("Please enter a valid year.\n")

    while not season_name:
        season_name_input = input("Season Name (spring|summer|fall|winter): ")
        if season_name_input.lower() in ["spring", "summer", "fall", "winter"]:
            season_name = season_name_input

        else:
            print("Please enter a valid season name.\n")

    anime_in_season = search_in_season_on_gogo(season_name,season_year)
    print("Anime found in {} {} Season: ".format(season_year, season_name))
    anime_names = []
    for anime in anime_in_season:
        anime_names.append(anime["name"])
    print_names(anime_names)
    selection = input("Selection: (e.g. 1, 1  3 or 1-3) \n>> ")
    if selection.__contains__("-"):
        selection_range = selection.strip(" ").split("-")
        for i in range(int(selection_range[0]) - 1, int(selection_range[1]) - 1, 1):
            selected.append(i)

    else:
        for i in selection.lstrip(" ").rstrip(" ").split(" "):
            selected.append(int(i) - 1)

    for value in selected:
        searches.append(anime_in_season[int(value)])
    return searches


def mal_cli(quality, no_season_search, ffmpeg, auto_update):
    m = MALCli(quality, no_season_search, ffmpeg, auto_update)
    if auto_update:
        m.download(mode="all")

    else:
        m.print_opts()
        m.take_input()


class MALCli:
    def __init__(self, quality, no_season_search=False, ffmpeg=False, auto=False):
        self.entry = entry()
        self.quality = quality
        self.m_class = mal
        self.ffmpeg = ffmpeg
        self.auto = auto
        self.no_season_search = no_season_search

    def print_opts(self):
        for i in mal_options:
            print(i)

    def take_input(self):
        while True:
            picked = input(colors.END + "Enter option: ")
            if picked == "a":
                self.add_anime()
            elif picked == "e":
                self.del_anime()
            elif picked == "l":
                self.list_animes()
            elif picked == "d":
                self.download(mode="latest")
            elif picked == "x":
                self.download(mode="all")
            elif picked == "w":
                self.binge_latest()
            elif picked == "q":
                self.quit()
            else:
                error("invalid input")

    def add_anime(self):
        show_entry = entry()
        is_season_search = False
        searches = []
        if (
            not self.no_season_search
            and input("Search for anime in Season? (y|n): \n>> ") == "y"
        ):
            searches = get_searches_from_gogo()

        else:
            searches.append(input("Search: "))

        #
        for search in searches:
            query_class = None
            if isinstance(search, dict):
                is_season_search = True
                links = [search["category_url"]]

            else:
                print("\nCurrent: ", search)
                query_class = query(search, show_entry)
                query_class.get_pages()
                links = query_class.get_links()

            if links == 0:
                sys.exit()

            if is_season_search:
                show_entry = entry()
                show_entry.show_name = search["name"]
                show_entry.category_url = search["category_url"]

            else:
                show_entry = query_class.pick_show()

            picked_ep = epHandler(show_entry).pick_ep_seasonal().ep
            mal.add_show(show_entry.show_name, show_entry.category_url, picked_ep)

        clear_console()
        self.print_opts()

    def del_anime(self):
        mal_list = mal.get_anime_list()
        mal_list = [x for x in mal_list]
        mal_names = [n["node"]["title"] for n in mal_list]
        print_names(mal_names)
        while True:
            inp = input("Enter Number: " + colors.CYAN)
            try:
                picked = mal_list[int(inp) - 1]["node"]["id"]
                break
            except:
                error("Invalid Input")

        mal.del_show(picked)
        clear_console()
        self.print_opts()

    def list_animes(self):
        for i in mal.get_anime_list():
            print(
                "==> Last watched EP: {} | {}".format(
                    i["node"]["my_list_status"]["num_episodes_watched"],
                    i["node"]["title"],
                )
            )

    def list_possible(self, latest_urls):
        for i in latest_urls:
            print(f"{colors.RED}{i}:")
            for j in latest_urls[i]["ep_list"]:
                print(f"{colors.CYAN}==> EP: {j[0]}")

    def download(self, mode="all"):
        if mode == "latest":
            urls = mal.latest_eps()

        else:
            urls = mal.latest_eps(all=True)

        if not urls:
            error("Nothing to download")
            return

        print("Stuff to be downloaded:")
        self.list_possible(urls)
        if not self.auto:
            input(f"{colors.RED}Enter to continue or CTRL+C to abort.")

        for i in urls:
            print(f"Downloading newest urls for {i}")
            show_entry = entry()
            show_entry.show_name = i
            for j in urls[i]["ep_list"]:
                show_entry.embed_url = ""
                show_entry.ep = j[0]
                show_entry.ep_url = j[1]
                url_class = videourl(show_entry, self.quality)
                url_class.stream_url()
                show_entry = url_class.get_entry()
                download(show_entry, self.ffmpeg).download()

        if not self.auto:
            clear_console()
            self.print_opts()

    def binge_latest(self):
        latest_eps = mal.latest_eps()
        print("Stuff to be watched:")
        self.list_possible(latest_eps)
        input(f"{colors.RED}Enter to continue or CTRL+C to abort.")
        ep_list = []
        ep_urls = []
        ep_dic = {}
        for i in latest_eps:
            for j in latest_eps[i]["ep_list"]:
                ep_list.append(j[0])
                ep_urls.append(j[1])

            ep_dic.update(
                {
                    i: {
                        "ep_urls": [x for x in ep_urls],
                        "eps": [x for x in ep_list],
                        "category_url": latest_eps[i]["category_url"],
                    }
                }
            )
            ep_list.clear()
            ep_urls.clear()

        binge(ep_dic, self.quality, mode="mal")

        clear_console()
        self.print_opts()

    def quit(self):
        sys.exit(0)

    def sync_mal_lists(self):
        pass


def main():
    args = parse_args()
    if args.delete:
        try:
            config.history_file_path.unlink()
            print(colors.RED + "Done")
        except FileNotFoundError:
            error("no history file found")

    elif args.download:
        download_cli(args.quality, args.ffmpeg, args.no_season_search)

    elif args.binge:
        binge_cli(args.quality)

    elif args.seasonal:
        seasonal_cli(args.quality, args.no_season_search, args.ffmpeg, args.auto_update)

    elif args.auto_update:
        seasonal_cli(args.quality, args.no_season_search, args.ffmpeg, args.auto_update)

    elif args.history:
        history_cli(args.quality)

    elif args.config:
        print(os.path.realpath(__file__).replace("cli.py", "config.py"))

    elif args.mal:
        mal_cli(args.quality, args.no_season_search, args.ffmpeg, args.auto_update)

    else:
        default_cli(args.quality)

    return
