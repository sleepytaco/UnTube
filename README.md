# UnTube
A simple, comprehensive YouTube playlist manager web app powered by [YouTube Data API V3](https://developers.google.com/youtube/v3/). Built with ❤ using Django, htmx and Bootstrap. 

## About

I built UnTube with the goal of making it easier to manage multiple YouTube playlists. UnTube makes it possible to bulk delete videos from a playlist, take care of duplicate or unavailable videos, bulk copy/move videos from one playlist to other playlists. All you have to do is log in with your Google account and import your playlists to access these basic features + more!

## Features

Apart from the base features mentioned above, UnTube offers more:

- Classify playlists into specific categories—for example, pin and favorite playlists/videos. For custom categories, you can create and assign tags to playlists.
- A comprehensive search bar to search every corner of all your playlist. The search bar is filled with features such as filter by tags, sort results based on parameters, etc
- Various overall and specific statistics and charts are provided for your playlists. For example, playlist duration, playlist video distribution per channel, etc.
- Set a playlist as 'watching' and see the remaining playlist duration update as you mark a video inside the playlist as watched.
- Import public playlists to your own UnTube collection. After importing, you can copy videos from that playlist into your own playlists.
- Set a gradient background ;)


## Walkthroughs

![UnTube bulk playlist operations](https://bakaabu.pythonanywhere.com/static/assets/imgs/features.70cfacf34e92.gif)

Check out the [landing page for UnTube](https://bakaabu.pythonanywhere.com/) for more GIF walkthroughs.

## Notes

I cannot be thankful enough for the existence of <b>htmx</b>. Most of the dynamic interactivity on this site was made possible due to htmx. When I began implementing core site features like moving, deleting, checking for updates, etc., I found myself writing a LOT of AJAX code each and every time, for even the simplest of interactivity. It was when I found htmx my development process sped up like crazy. Who would have thought that instead of replacing the whole page with the response, just replacing a particular target element with the HttpResponse would do wonders? Some of the major places I've used htmx on this site:

-    <b>HTMX Triggers</b> htmx offers various triggers upon which it sends requests. One example is the <code>load</code> trigger. After the dashboard finishes loading, I've set up htmx to automatically send a GET request to the backend (this only happens once upon the page load) to check for playlist updates. From the backend, the update status is sent back via a HttpResponse which htmx promptly loads into a target div I specified. That way I did not need to check for updates inside the main view that loaded the page. In a way, htmx helped me check for updates in the "background". I've used this <code>load</code> trigger many other places on the site, one other example is the playlist completion time info is loaded after the playlist page is loaded.<br>
    Instead of sending requests on <code>load</code>, it is also possible to send htmx requests when any HTML element is <code>click</code>ed or <code>revealed</code>. I've used this <Code>click</code> trigger on the mark playlist/video as favorite buttons and the mark videos as watched buttons. Below, I discuss about using the <code>revealed</code> to achieve infinite scrolling.
-    <b>Active Search</b> The whole search page heavily relies on htmx. On the frontend, via htmx the text field (as well as the select and radio buttons) is hooked up to automatically send requests with the search query to the backend right after certain milliseconds of typing. In Django, I've set up a view to receive these htmx requests and send back a HttpResponse using a template loader. htmx then loads the received response into a target search results div that I've set up. Check out this [search example](https://htmx.org/examples/active-search/) from htmx's website.
-    <b>Infinite Scrolling</b> For playlists with more than 50 videos, the next 50 videos are automatically loaded onto the screen only when the user scrolls down to the bottom. htmx's <code>hx-trigger="revealed"</code> and <code>hx-swap="afterend"</code> attributes helped me achieve this functionality. When the 50th video is revealed on the screen, htmx makes a GET request to the backend to get the next 50 videos (if available) and appends the HttpResponse after the 50th video. Until htmx gets back a response from the backend, it can be set up to show the user a loading spinner!<br>
    The main advantage of this feature was that for playlists with 100s or even 1000s of videos, it only needs to load the first 50 videos every time, vastly improving the playlist page load speed.
    
Additional interactive features such as the progress bar and tagging playlist were all made possible because of htmx. Any questions on how I've implemented some of the features on this site? Please send me an email at [abukhan363@gmail.com](mailto:abukhan363@gmail.com) with your feedback and questions. I will be happy to share my code and thought process to illustrate how I implemented the site's features using htmx. 


## Libraries/Resources Used

- [Bootstrap5]() - Whole UI of the site was built using Bootstrap.
- [htmx](https://htmx.org) - Used this beautiful library all throughout my site to help simplify making AJAX calls and focus on building highly interactive site with just a little bit of code.
- [fontawesome](fontawesome.com/) - All the lovely icons are provided by fontawesome.
- [Charts.js](https://www.chartjs.org/) - All the charts that you see on the site were made using Charts.js
- [Choices.js](https://github.com/Choices-js/Choices) - The search bar uses this library to effectively search through 100s of channels or tags.
- [Clipboard.js](https://clipboardjs.com/) - The copy-paste buttons on the site were made possible because of this library.
- [robohash](https://robohash.org/) - Used robohash to generate a unique robot profile picture for users based on their username.
- [SVG Loaders](https://github.com/SamHerbert/SVG-Loaders) - SVG loader signs found all over the site were taken from SamHerbert. All the previews of the loaders can be found at [his site](https://samherbert.net/svg-loaders/)
- [Bleach](https://pypi.org/project/bleach/) - Utilized this wherever I took in input from the user (import playlists, video notes, labels, tags, etc.)
- [djhtml](https://github.com/rtts/djhtml) - Django/Jinja template indenter. My HTML templates were getting messy pretty quickly, so using an indenter saved me a lot of time.


## To Do 
- Verify my application with Google to remove the 'unverified app warning' screen when a user first signs up.
- Request Google to increase the quota limit for my web app.
- Add tutorial to setup and run this project locally.
