#!/usr/bin/env python3

import argparse, requests, json, pickle, os, time, random, http.client, httplib2, datetime
from moviepy.editor import VideoFileClip, concatenate_videoclips
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

def run(args=None):
    game = args.game
    number = args.number
    days_ago = args.days_ago
    oauth = get_oauth()
    game_id = get_game_id(game, oauth)
    clips = get_clips(game_id, oauth, number, days_ago)
    videos = download_clips(clips)
    # concatenate_clips(videos)
    delete_clips(videos)
    # upload_video()


def get_oauth():
    url = 'https://id.twitch.tv/oauth2/token?'
    params = {"client_id":"mxnht2zsdidy2roz676lo8qmmv8q8o", "client_secret":"541lihcbx8mrmznmsbh2ip7tj27uwo", "grant_type":"client_credentials"}
    response = requests.post(url, params).text
    return json.loads(response)["access_token"]



def get_game_id(game, oauth):
    url = 'https://api.twitch.tv/helix/games?name=' + game
    headers = {"Authorization":"Bearer " + oauth, "Client-Id":"mxnht2zsdidy2roz676lo8qmmv8q8o"}
    response = requests.get(url, headers=headers).text
    return json.loads(response)["data"][0]["id"]



def get_clips(game_id, oauth, number, days_ago):
    today = datetime.date.today()
    week_ago = (today - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")
    start_date = week_ago + "T00:00:00.00Z"
    url = 'https://api.twitch.tv/helix/clips?'
    params = {"game_id":game_id, "first":number, "started_at":start_date}
    headers = {"Authorization":"Bearer " + oauth, "Client-Id":"mxnht2zsdidy2roz676lo8qmmv8q8o"}
    response = requests.get(url, params, headers=headers).text
    response_json = json.loads(response)
    clips = []
    for data in response_json["data"]:
        url = data["thumbnail_url"]
        splice_index = url.index("-preview")
        clips.append(url[:splice_index] + ".mp4")
    return clips



def download_clips(clips):
    videos = []
    for i in range(len(clips)):
        r = requests.get(clips[i], stream=True)
        name = str(i) + ".mp4"
        with open(name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        videos.append(name)
    return videos



def delete_clips(videos):
    for video in videos:
        os.remove(video)




def concatenate_clips(videos):
    vfcs = []
    for video in videos:
        vfc = VideoFileClip(video, target_resolution=(1080, 1920))
        vfcs.append(vfc)
    final_clip = concatenate_videoclips(vfcs)
    final_clip.write_videofile("final.mp4", temp_audiofile="temp-audio.m4a", remove_temp=True, audio_codec="aac")




def Create_Service(client_secret_file, api_name, api_version, *scopes):
    # print(client_secret_file, api_name, api_version, scopes, sep='-')
    CLIENT_SECRET_FILE = client_secret_file
    API_SERVICE_NAME = api_name
    API_VERSION = api_version
    SCOPES = [scope for scope in scopes[0]]
    # print(SCOPES)

    cred = None

    pickle_file = f'token_{API_SERVICE_NAME}_{API_VERSION}.pickle'
    # print(pickle_file)

    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as token:
            cred = pickle.load(token)

    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            cred = flow.run_local_server()

        with open(pickle_file, 'wb') as token:
            pickle.dump(cred, token)

    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=cred)
        print(API_SERVICE_NAME, 'service created successfully')
        return service
    except Exception as e:
        print('Unable to connect.')
        print(e)
        return None



def convert_to_RFC_datetime(year=1900, month=1, day=1, hour=0, minute=0):
    dt = datetime.datetime(year, month, day, hour, minute, 0).isoformat() + 'Z'
    return dt



def upload_video():
    CLIENT_SECRET_FILE = 'client_secret.json'
    API_NAME = 'youtube'
    API_VERSION = 'v3'
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

    service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

    request_body = {
        'snippet': {
            'categoryId': 20,
            'title': 'Test upload',
            'description': 'Test description',
            'tags': ['Test', 'multiple', 'tags']
        },
        'status': {
            'privacyStatus': 'private',
            'selfDeclaredMadeForKids': False,
        }
    }

    mediaFile = MediaFileUpload('final.mp4', chunksize=-1, resumable=True)

    response_upload = service.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=mediaFile
    )

    # Explicitly tell the underlying HTTP transport library not to retry, since
    # we are handling retry logic ourselves.
    httplib2.RETRIES = 1

    # Maximum number of times to retry before giving up.
    MAX_RETRIES = 10

    # Always retry when these exceptions are raised.
    RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, http.client.NotConnected,
        http.client.IncompleteRead, http.client.ImproperConnectionState,
        http.client.CannotSendRequest, http.client.CannotSendHeader,
        http.client.ResponseNotReady, http.client.BadStatusLine)

    # Always retry when an apiclient.errors.HttpError with one of these status
    # codes is raised.
    RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print("Uploading file...")
            status, response = response_upload.next_chunk()
            if response is not None:
                if 'id' in response:
                    print("Video id '%s' was successfully uploaded." % response['id'])
            else:
                exit("The upload failed with an unexpected response: %s" % response)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status,e.content)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = "A retriable error occurred: %s" % e

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                exit("No longer attempting to retry.")

            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print("Sleeping %f seconds and then retrying..." % sleep_seconds)
            time.sleep(sleep_seconds)



def main():
    parser=argparse.ArgumentParser(description="Download, concatenate, and upload the 10 most viewed Twitch clips of the specified game in the past week")
    parser.add_argument("-g",help="Game name",dest="game",type=str,required=True)
    parser.add_argument("-n",help="Number of clips to use",dest="number",type=str,default="10")
    parser.add_argument("-d",help="Number of days ago that clips started",dest="days_ago",type=int,default=7)
    parser.set_defaults(func=run)
    args=parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
