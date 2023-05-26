def deep_update(base_dict, update_with):
    """
    Updates the base_dict (eg. settings/base.py settings) with the values present
    in the update_with dict
    """
    # iterate over items in the update_with dict
    for key, value in update_with.items():
        if isinstance(value, dict):  # update_with dict value is a dict, i.e. update_with[key] = {}
            base_dict_value = base_dict.get(key)

            # check if base_dict value is also a dict
            if isinstance(base_dict_value, dict):  # check if base_dict[key] = {}
                deep_update(base_dict_value, value)  # recurse
            else:
                base_dict[key] = value  # else update the base dict with whatever dict value in update_with
        else:
            base_dict[key] = value

    # return the updated base_dict
    return base_dict
