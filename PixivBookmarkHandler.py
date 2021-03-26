import os
import sys
from datetime import time

from bs4 import BeautifulSoup

import PixivArtistHandler
import PixivConstant
import PixivDownloadHandler
import PixivHelper
import PixivImageHandler
from PixivBookmark import PixivBookmark, PixivNewIllustBookmark
from PixivGroup import PixivGroup


def process_bookmark(caller,
                     config,
                     hide='n',
                     start_page=1,
                     end_page=0):
    br = caller.__br__

    try:
        total_list = list()
        print(f"My Member Id = {br._myId}")
        if hide != 'o':
            print("Importing Bookmarks...")
            total_list.extend(get_bookmarks(caller, config, False, start_page, end_page, br._myId))
        if hide != 'n':
            print("Importing Private Bookmarks...")
            total_list.extend(get_bookmarks(caller, config, True, start_page, end_page, br._myId))
        print(f"Result: {str(len(total_list))} items.")
        i = 0
        current_member = 1
        for item in total_list:
            print("%d/%d\t%f %%" % (i, len(total_list), 100.0 * i / float(len(total_list))))
            i += 1
            prefix = "[{0} of {1}]".format(current_member, len(total_list))
            PixivArtistHandler.process_member(caller,
                                              config,
                                              item.memberId,
                                              user_dir=item.path,
                                              title_prefix=prefix)
            current_member = current_member + 1

        if len(total_list) > 0:
            print("%d/%d\t%f %%" % (i, len(total_list), 100.0 * i / float(len(total_list))))
        else:
            print("Cannot find any followed member.")
    except KeyboardInterrupt:
        raise
    except BaseException:
        PixivHelper.print_and_log('error', 'Error at process_bookmark(): {0}'.format(sys.exc_info()))
        raise


def process_image_bookmark(caller,
                           config,
                           hide='n',
                           start_page=1,
                           end_page=0,
                           tag=None,
                           use_image_tag=False):
    try:
        print("Importing image bookmarks...")
        totalList = list()
        private_list = list()
        public_list = list()
        image_count = 1
        total_bookmark_count = 0

        if hide == 'n':
            (public_list, total_bookmark_count) = get_image_bookmark(caller, config, False, start_page, end_page, tag, use_image_tag)
        elif hide == 'y':
            # public and private image bookmarks
            (public_list, total_bookmark_count_pub) = get_image_bookmark(caller, config, False, start_page, end_page, tag, use_image_tag)
            (private_list, total_bookmark_count_priv) = get_image_bookmark(caller, config, True, start_page, end_page, tag, use_image_tag)
            total_bookmark_count = total_bookmark_count_pub + total_bookmark_count_priv
        else:
            (private_list, total_bookmark_count) = get_image_bookmark(caller, config, True, start_page, end_page, tag, use_image_tag)
        totalList.extend(private_list)
        totalList.extend(public_list)

        PixivHelper.print_and_log('info', f"Found {len(totalList)} of {total_bookmark_count} possible image(s) .")
        for item in totalList:
            print("Image #" + str(image_count))
            result = PixivImageHandler.process_image(caller,
                                                     config,
                                                     artist=None,
                                                     image_id=item,
                                                     search_tags=tag)
            image_count = image_count + 1
            PixivHelper.wait(result, config)

        print("Done.\n")
    except KeyboardInterrupt:
        raise
    except BaseException:
        PixivHelper.print_and_log('error', 'Error at process_image_bookmark(): {0}'.format(sys.exc_info()))
        raise


def process_new_illust_from_bookmark(caller,
                                     config,
                                     page_num=1,
                                     end_page_num=0):
    br = caller.__br__
    parsed_page = None
    try:
        print("Processing New Illust from bookmark")
        i = page_num
        image_count = 1
        flag = True
        while flag:
            print("Page #" + str(i))
            url = 'https://www.pixiv.net/bookmark_new_illust.php?p=' + str(i)
            if config.r18mode:
                url = 'https://www.pixiv.net/bookmark_new_illust_r18.php?p=' + str(i)

            PixivHelper.print_and_log('info', "Source URL: " + url)
            page = br.open(url)
            parsed_page = BeautifulSoup(page.read().decode("utf-8"), features="html5lib")
            pb = PixivNewIllustBookmark(parsed_page)
            if not pb.haveImages:
                print("No images!")
                break

            for image_id in pb.imageList:
                print("Image #" + str(image_count))
                result = PixivImageHandler.process_image(caller,
                                                         config,
                                                         artist=None,
                                                         image_id=int(image_id))
                image_count = image_count + 1

                if result == PixivConstant.PIXIVUTIL_SKIP_OLDER:
                    flag = False
                    break

                PixivHelper.wait(result, config)
            i = i + 1

            page.close()
            parsed_page.decompose()
            del parsed_page

            # Non premium is only limited to 100 page
            # Premium user might be limited to 5000, refer to issue #112
            if (end_page_num != 0 and i > end_page_num) or i > 5000 or pb.isLastPage:
                print("Limit or last page reached.")
                flag = False

        print("Done.")
    except KeyboardInterrupt:
        raise
    except BaseException:
        PixivHelper.print_and_log('error', 'Error at process_new_illust_from_bookmark(): {0}'.format(sys.exc_info()))
        if parsed_page is not None:
            filename = "Dump for New Illust from bookmark.html"
            PixivHelper.dump_html(filename, parsed_page)
        raise


def process_from_group(caller,
                       config,
                       group_id,
                       limit=0,
                       process_external=True):
    br = caller.__br__
    json_response = None
    try:
        print("Download by Group Id")
        if limit != 0:
            print("Limit: {0}".format(limit))
        if process_external:
            print("Include External Image: {0}".format(process_external))

        max_id = 0
        image_count = 0
        flag = True
        while flag:
            url = "https://www.pixiv.net/group/images.php?format=json&max_id={0}&id={1}".format(max_id, group_id)
            PixivHelper.print_and_log('info', "Getting images from: {0}".format(url))
            response = br.open(url)
            json_response = response.read()
            response.close()
            group_data = PixivGroup(json_response)
            max_id = group_data.maxId
            if group_data.imageList is not None and len(group_data.imageList) > 0:
                for image in group_data.imageList:
                    if image_count > limit and limit != 0:
                        flag = False
                        break
                    print("Image #{0}".format(image_count))
                    print("ImageId: {0}".format(image))
                    result = PixivImageHandler.process_image(caller,
                                                             config,
                                                             image_id=image)
                    image_count = image_count + 1
                    PixivHelper.wait(result, config)

            if process_external and group_data.externalImageList is not None and len(group_data.externalImageList) > 0:
                for image_data in group_data.externalImageList:
                    if image_count > limit and limit != 0:
                        flag = False
                        break
                    print("Image #{0}".format(image_count))
                    print("Member Id   : {0}".format(image_data.artist.artistId))
                    PixivHelper.safePrint("Member Name  : " + image_data.artist.artistName)
                    print("Member Token : {0}".format(image_data.artist.artistToken))
                    print("Image Url   : {0}".format(image_data.imageUrls[0]))

                    filename = PixivHelper.make_filename(config.filenameFormat,
                                                         imageInfo=image_data,
                                                         tagsSeparator=config.tagsSeparator,
                                                         tagsLimit=config.tagsLimit,
                                                         fileUrl=image_data.imageUrls[0],
                                                         useTranslatedTag=config.useTranslatedTag,
                                                         tagTranslationLocale=config.tagTranslationLocale)
                    filename = PixivHelper.sanitize_filename(filename, config.rootDirectory)
                    PixivHelper.safePrint("Filename  : " + filename)
                    (result, filename) = PixivDownloadHandler.download_image(caller,
                                                                             image_data.imageUrls[0],
                                                                             filename,
                                                                             url,
                                                                             config.overwrite,
                                                                             config.retry,
                                                                             backup_old_file=config.backupOldFile)
                    PixivHelper.get_logger().debug("Download %s result: %s", filename, result)
                    if config.setLastModified and filename is not None and os.path.isfile(filename):
                        ts = time.mktime(image_data.worksDateDateTime.timetuple())
                        os.utime(filename, (ts, ts))

                    image_count = image_count + 1

            if (group_data.imageList is None or len(group_data.imageList) == 0) and \
               (group_data.externalImageList is None or len(group_data.externalImageList) == 0):
                flag = False
            print("")

    except BaseException:
        PixivHelper.print_and_log('error', 'Error at process_from_group(): {0}'.format(sys.exc_info()))
        if json_response is not None:
            filename = f"Dump for Download by Group {group_id}.json"
            PixivHelper.dump_html(filename, json_response)
        raise


def export_bookmark(caller,
                    config,
                    filename,
                    hide='n',
                    start_page=1,
                    end_page=0,
                    member_id=None):
    try:
        total_list = list()
        if hide != 'o':
            print("Importing Bookmarks...")
            total_list.extend(get_bookmarks(caller, config, False, start_page, end_page, member_id))
        if hide != 'n':
            print("Importing Private Bookmarks...")
            total_list.extend(get_bookmarks(caller, config, True, start_page, end_page, member_id))
        print("Result: ", str(len(total_list)), "items.")
        PixivBookmark.exportList(total_list, filename)
    except KeyboardInterrupt:
        raise
    except BaseException:
        PixivHelper.print_and_log('error', 'Error at export_bookmark(): {0}'.format(sys.exc_info()))
        raise


def get_bookmarks(caller, config, hide, start_page=1, end_page=0, member_id=None):
    br = caller.__br__

    """Get User's bookmarked artists """
    total_list = list()
    i = start_page
    limit = 24
    offset = 0
    is_json = False

    while True:
        if end_page != 0 and i > end_page:
            print('Limit reached')
            break
        PixivHelper.print_and_log('info', f'Exporting page {i}')
        if member_id:
            is_json = True
            offset = limit * (i - 1)
            url = f'https://www.pixiv.net/ajax/user/{member_id}/following?offset={offset}&limit={limit}'
        else:
            url = f'https://www.pixiv.net/bookmark.php?type=user&p={i}'
        if hide:
            url = url + "&rest=hide"
        else:
            url = url + "&rest=show"

        PixivHelper.print_and_log('info', f"Source URL: {url}")

        page = br.open_with_retry(url)
        page_str = page.read().decode('utf8')
        page.close()

        bookmarks = PixivBookmark.parseBookmark(page_str,
                                                root_directory=config.rootDirectory,
                                                db_path=config.dbPath,
                                                locale=br._locale,
                                                is_json=is_json)

        if len(bookmarks) == 0:
            print('No more data')
            break
        total_list.extend(bookmarks)
        i = i + 1
        print(str(len(bookmarks)), 'items')
        PixivHelper.wait(config=config)
    return total_list


def get_image_bookmark(caller, config, hide, start_page=1, end_page=0, tag=None, use_image_tag=False):
    """Get user's image bookmark"""
    br = caller.__br__
    total_list = list()
    i = start_page
    offset = 0
    limit = 48
    member_id = br._myId
    total_bookmark_count = 0
    encoded_tag = ''

    while True:
        if end_page != 0 and i > end_page:
            print("Page Limit reached: " + str(end_page))
            break

        # https://www.pixiv.net/ajax/user/189816/illusts/bookmarks?tag=&offset=0&limit=48&rest=show
        show = "show"
        if hide:
            show = "hide"

        if tag is not None and len(tag) > 0:
            encoded_tag = PixivHelper.encode_tags(tag)
        offset = limit * (i - 1)
        PixivHelper.print_and_log('info', f"Importing user's bookmarked image from page {i}")

        url = f"https://www.pixiv.net/ajax/user/{member_id}/illusts/bookmarks?tag={encoded_tag}&offset={offset}&limit={limit}&rest={show}"
        if use_image_tag:  # don't filter based on user's bookmark tag
            url = f"https://www.pixiv.net/ajax/user/{member_id}/illusts/bookmarks?tag=&offset={offset}&limit={limit}&rest={show}"
            PixivHelper.print_and_log('info', f"Using image tag: {tag}")

        PixivHelper.print_and_log('info', f"Source URL: {url}")
        page = br.open(url)
        page_str = page.read().decode('utf8')
        page.close()

        if use_image_tag:
            (bookmarks, total_bookmark_count) = PixivBookmark.parseImageBookmark(page_str, image_tags_filter=tag)
        else:
            (bookmarks, total_bookmark_count) = PixivBookmark.parseImageBookmark(page_str)

        total_list.extend(bookmarks)
        if len(bookmarks) == 0 and not use_image_tag:
            print("No more images.")
            break
        elif use_image_tag and total_bookmark_count / limit < i:
            print("Last page reached.")
            break
        else:
            print(f" found {len(bookmarks)} images.")

        i = i + 1

        # Issue#569
        PixivHelper.wait(config=config)

    return (total_list, total_bookmark_count)
