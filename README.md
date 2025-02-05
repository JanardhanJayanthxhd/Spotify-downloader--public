
# SaveStreamz

A webapp that is used to download Spotify playlist/album/track or Youtube audio.



## Tech Stack

**Client:** HTML, JS, CSS(Bootstarp)

**Server:** Python(Django), Celery, Rabbitmq, Sqlite3

## Requirements

Pytubefix(version 8.12.1) package requires <a href="https://nodejs.org/en">node.js</a> installed in pc/machine.


## Environment Variables

To run this project, you will need to add the following environment variables to your .env file inside django app(webpage in this case).

`CLIENT_ID` - from spotify dashboard

`CLIENT_SECRET` - from spotify dashboard


## Installation

Install all the required packages using `pip`
```bash
  > pip install -r requirements.txt
```
Install and start rabbitmq-server in Linux or Windows WSL
```bash
  $ sudo apt-get install rabbitmq-server
  $ sudo service rabbitmq-server start
```
Start a celery worker in a seperate terminal inside project directory with environment activated.
```bash
  > celery -A downloader worker -P gevent
```
Run the django project with environment activated:
```bash
    > python manage.py runserver
```

## Screenshots

(for demo see > `ss/rmd vid.gif`)

<details><summary>Home page</summary>
<img src="ss/home page.png">
</details>

<details><summary>Youtube download page</summary>
<img src="ss/youtube video.png">
</details>

<details><summary>Spotify playlist page</summary>
<img src="ss/spotify playlist.png">
</details>

<details><summary>Spotify track page</summary>
<img src="ss/spotify track.png">
</details>

