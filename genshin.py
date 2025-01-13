import json
import logging
import os
import pathlib
import re
from collections import defaultdict
from copy import deepcopy

import dotenv
import requests
from tqdm import tqdm

dotenv.load_dotenv()


class HoyoLabException(Exception):
    pass


class ItemType:
    CHARACTER = "Character"
    WEAPON = "Weapon"


class HoyoLab:

    BASE_CALCULATE_URL = "https://sg-public-api.hoyolab.com/event/calculateos/"
    AVATAR_LIST = BASE_CALCULATE_URL + "avatar/list"
    WEAPON_LIST = BASE_CALCULATE_URL + "weapon/list"
    BATCH_COMPUTE = BASE_CALCULATE_URL + "batch_compute"

    def __init__(self, cookies: str, uid: str, region: str = "os_asia", logging_level: int = logging.INFO):
        self.headers = {
            "cookie": cookies,
            "User-Agent": "NepScript/1.0"
        }
        self.uid = uid
        self.region = region

        self._setup_logger(logging_level)
        self.logger.info("HoyoLab initialized")
        self.logger.debug(f"Cookies: {cookies}")
        self.logger.debug(f"UID: {uid}")
        self.logger.debug(f"Region: {region}")

    def _setup_logger(self, level: int):
        self.logger = logging.getLogger("GenshinMats")
        self.logger.setLevel(level)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def _req(self, url: str, body: dict, headers: dict, method: str = "GET"):
        self.logger.debug(f"Making {method} request to {url}")
        r = requests.request(method, url, headers=headers, json=body)
        r.raise_for_status()

        data = r.json()
        if data["retcode"] != 0:
            raise HoyoLabException(data["message"])
        elif "HasUserInfo" in data["data"].keys() and not data["data"]["HasUserInfo"]:
            raise HoyoLabException("Either the UID or Cookies are invalid.")
        return data["data"]

    def _get(self, url: str, body: dict, headers: dict):
        return self._req(url, body, headers, "GET")

    def _post(self, url: str, body: dict, headers: dict):
        return self._req(url, body, headers, "POST")

    def _get_all_items(self, type: ItemType):
        body = {"element_attr_ids": [], "weapon_cat_ids": [], "page": 1, "size": 999, "is_all": True, "lang": "en-us"}
        url = self.AVATAR_LIST if type == ItemType.CHARACTER else self.WEAPON_LIST
        return self._post(url, body, self.headers)

    def get_all_avatars(self):
        return self._get_all_items(ItemType.CHARACTER)

    def get_all_weapons(self):
        return self._get_all_items(ItemType.WEAPON)

    def calculate(self, items: list[dict]):
        self.logger.debug(f"Calculating materials for {len(items)} items")
        body = {
            "items": items,
            "uid": self.uid,
            "region": self.region
        }
        return self._post(self.BATCH_COMPUTE, body, self.headers)

    def _generate_item_data(self, item, type: ItemType):
        self.logger.debug(f"Generating item data for {item['name']} of type {type}")
        if type not in ItemType.__dict__.values():
            raise ValueError("Invalid item type")

        if type == ItemType.CHARACTER:
            return {
                "avatar_id": item["id"],
                "avatar_level_current": 1,
                "avatar_level_target": 90,
                "element_attr_id": item["element_attr_id"],
                "skill_list": [{"id": skill["group_id"], "level_current": 1, "level_target": 10} for skill in item["skill_list"]],
                "weapon": {}
            }
        elif type == ItemType.WEAPON:
            return {
                "weapon": {
                    "id": item["id"],
                    "level_current": 1,
                    "level_target": item["max_level"],
                }
            }

    def find_min_entity_needed(self, item_materials_dict: dict):
        self.logger.info("Finding minimum entities needed to cover all materials")

        item_materials_dict_copy = deepcopy(item_materials_dict)
        all_materials = set()
        for materials in item_materials_dict_copy.values():
            all_materials.update(set(materials))

        selected_entities = []
        covered_materials = set()

        self.logger.debug(f"Total materials: {all_materials}")
        while covered_materials != all_materials:
            best_entity = None
            best_coverage = set()

            self.logger.debug(f"Remaining materials: {all_materials - covered_materials}")
            for entity, materials in item_materials_dict_copy.items():
                new_coverage = set(materials) - covered_materials
                if len(new_coverage) > len(best_coverage):
                    best_entity = entity
                    best_coverage = new_coverage

            selected_entities.append(int(best_entity))
            covered_materials.update(best_coverage)
            del item_materials_dict_copy[best_entity]

        return selected_entities

    def get_all_materials(self):
        self.logger.info("Getting materials all avatars and weapons available")
        self.avatars = self.get_all_avatars()["list"]
        self.weapons = self.get_all_weapons()["list"]

        json_path = pathlib.Path("genshin_mats.json")
        if json_path.exists():
            with open(json_path) as f:
                data = json.load(f)

            avatar_ids = [item["id"] for item in self.avatars]
            traveler_dupe_count = (avatar_ids.count(10000005) * 2)  # For both aether and lumine

            self.logger.debug(f"Number of cached items: {len(data)}")
            self.logger.debug(f"Number of fetched items: {len(self.avatars) + len(self.weapons)}")
            self.logger.debug(f"Number of traveler elements currently available: {int((traveler_dupe_count) / 2)}")

            if len(data) == len(self.avatars) + len(self.weapons) - traveler_dupe_count + 2:
                self.logger.info("No new avatars or weapons, using cached data")
                return data
            else:
                self.logger.info("New avatars or weapons found, recalculating")
        else:
            self.logger.info("No cached data found, doing first time calculation")

        avatar_body = [self._generate_item_data(avatar, ItemType.CHARACTER) for avatar in self.avatars]
        weapon_body = [self._generate_item_data(weapon, ItemType.WEAPON) for weapon in self.weapons]

        response = self.calculate(avatar_body + weapon_body)
        item_materials_dict = {
            item["id"]: {material["id"] for material in (item_mat["avatar_consume"] + item_mat["avatar_skill_consume"] + item_mat["weapon_consume"])}
            for item, item_mat in zip(self.avatars + self.weapons, response["items"])
        }
        item_materials_dict = {item: sorted(list(materials)) for item, materials in item_materials_dict.items()}
        with open(json_path, "w") as f:
            json.dump(item_materials_dict, f, indent=4)

        return item_materials_dict

    def calculate_selected_materials(self, entities: list[str], count: int = 50):
        self.logger.info(f"Calculating materials for {len(entities) * count} entities")

        avatars_to_select = [avatar for avatar in self.avatars if avatar["id"] in entities]
        weapons_to_select = [weapon for weapon in self.weapons if weapon["id"] in entities]

        avatar_body = [item for avatar in avatars_to_select for item in [self._generate_item_data(avatar, ItemType.CHARACTER)] * count]
        weapon_body = [item for weapon in weapons_to_select for item in [self._generate_item_data(weapon, ItemType.WEAPON)] * count]

        self.logger.debug(f"Number of avatars: {len(avatar_body)}")
        self.logger.debug(f"Number of weapons: {len(weapon_body)}")

        len_avatars = len(avatar_body)
        len_weapons = len(weapon_body)

        for avatar, weapon in zip(avatar_body, weapon_body):
            avatar["weapon"] = weapon["weapon"]

        calculate_list = []
        if len_avatars > len_weapons:
            calculate_list = avatar_body + avatar_body[len_weapons:]
        else:
            calculate_list = avatar_body + weapon_body[len_avatars:]

        calculate_list_chunked = [calculate_list[i:i + 200] for i in range(0, len(calculate_list), 200)]

        result = []
        for chunk in tqdm(calculate_list_chunked, desc="Calculating materials", unit="chunk", leave=False):
            response = self.calculate(chunk)
            available_materials = {material["id"]: material["num"] for material in response["available_material"]}
            for material in response["overall_consume"]:
                material["extra"] = available_materials.get(material["id"], 0)
                result.append(material)

        return result

    def process_item_iterative(self, materials_group_to_check: list[list[str]], good_result: dict):
        self.logger.info("Processing items iteratively")
        for item_list in materials_group_to_check:
            self.logger.debug(f"Processing item list: {item_list}")
            next_valid_index = None
            for current_index, sub_item in enumerate(item_list):
                if good_result[sub_item]["extra"] > 0:

                    if next_valid_index is None or good_result[item_list[next_valid_index]]["extra"] == 0:
                        next_valid_index = None
                        for i in range(current_index + 1, len(item_list)):
                            if good_result[item_list[i]]["extra"] == 0:
                                next_valid_index = i
                                break

                    if next_valid_index is not None:
                        adjustment_factor = 3 ** (next_valid_index - current_index)
                        good_result[item_list[next_valid_index]]["num"] -= int(good_result[sub_item]["extra"] / adjustment_factor)

    def clean_up_materials(self, materials: list[dict]):
        self.logger.info("Cleaning up materials")

        cleaned_items = {}
        for material in materials:
            good_name = " ".join(word.capitalize() for word in re.split(r"[- ]", material["name"].strip('"')))
            good_name = re.sub(r"[\W]", "", good_name)

            new_num = material["num"] - material["lack_num"] + material["extra"]

            if good_name not in cleaned_items or new_num > cleaned_items[good_name]["num"]:
                cleaned_items[good_name] = {
                    "good": good_name,
                    "id": material["id"],
                    "extra": material["extra"],
                    "num": new_num
                }

        sorted_cleaned_items = sorted(cleaned_items.values(), key=lambda x: x["id"], reverse=True)
        material_groups = defaultdict(list)

        four_tiers = material_groups[4]
        three_tiers = material_groups[3]

        for item in sorted_cleaned_items:
            item_id = item["id"]
            # > 114000 is for weapon ascension materials
            # 104100 < item_id < 104300 is for ascension gems
            if item_id > 114000 or (104100 < item_id < 104300):
                four_tiers.append(item)

            # 104300 < item_id < 113000 is for books
            # 104319 is for Crown of Insight
            elif 104300 < item_id < 113000 and item_id != 104319:
                three_tiers.append(item)

        materials_group_to_check = [
            [d["good"] for d in material_groups[tier][i:i + tier]][::-1]
            for tier in material_groups
            for i in range(0, len(material_groups[tier]), tier)
        ]

        materials_group_to_check.reverse()
        self.process_item_iterative(materials_group_to_check, cleaned_items)
        return cleaned_items

    def dump_good(self, good_result: dict, filename: str):
        self.logger.info(f"Dumping good materials to {filename}")
        good_json = {
            "format": "GOOD",
            "version": 2,
            "nep_version": "0.1",
            "source": "NepScript",
            "materials": {d['good']: d['num'] for d in good_result.values()}
        }
        with open(filename, "w") as f:
            json.dump(good_json, f, indent=4)


if __name__ == "__main__":
    cookies = os.getenv("COOKIES")
    uid = os.getenv("UID")

    if not cookies or not uid:
        raise HoyoLabException("Cookies or UID not found in environment variables")

    hoyolab = HoyoLab(cookies, uid)  # logging_level=logging.DEBUG if you want to see debug logs
    materials = hoyolab.get_all_materials()
    entities = hoyolab.find_min_entity_needed(materials)
    # Increase or decrease count as needed, good estimate is around (your highest material count / 50)
    # For example, if you have 3000 damaged masks. So, 3000 / 50 = 60
    # Default is 50
    materials_in_inventory = hoyolab.calculate_selected_materials(entities)
    cleaned_materials = hoyolab.clean_up_materials(materials_in_inventory)
    hoyolab.dump_good(cleaned_materials, "good_materials.json")
