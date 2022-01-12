from flox import Flox, utils
import json
import webbrowser
from github import Github
from github.GithubException import BadCredentialsException, RateLimitExceededException
from phrases import phrases
from random import choice

class GithubNotifications(Flox):

    def _init_github(self):
        self.gh = Github(self.settings('token', ''))

    @utils.cache('gh.json', max_age=60)
    def main_search(self):
        self._init_github()
        notifications = self.gh.get_user().get_notifications()
        for notification in notifications:
            url = notification.subject.url
            if notification.subject.type == "PullRequest":
                pr = notification.get_pull_request()
                url = pr.html_url
            elif notification.subject.type == "Issue":
                url = notification.get_issue().html_url
            elif notification.subject.type == "Release":
                header, data = notification._requester.requestJsonAndCheck("GET", notification.subject.url)
                url = data["html_url"]
            else:
                url = notification.repository.html_url
            subtitle = f"{notification.reason.title()} - {notification.repository.html_url}" 
            self.add_item(
                title=notification.subject.title,
                subtitle=subtitle,
                method=self.open_url,
                parameters=[url, notification.id],
                context=[notification.id]
            )
        return self._results

    def filter_results(self, query):
        results = []
        for result in self._results:
            if query.lower() in result['Title'].lower():
                results.append(result)
        self._results = results

    
    def query(self, query):
        try:
            self._results = self.main_search()
            self.filter_results(query)
        except BadCredentialsException:
            self.add_item(
                title="Could not login to Github",
                subtitle="Bad or missing Personal Access Token."
            )
        except RateLimitExceededException:
            self.add_item(
                title="Rate limit exceeded",
                subtitle="You have reached the rate limit for this hour."
            )
        if len(self._results) == 0:
            subtitle = choice(phrases)
            self.add_item(
                title="No notifications",
                subtitle=subtitle
            )
        return self._results

    def context_menu(self, data):
        try:
            id = data[0]
        except (IndexError, TypeError):
            return
        else:
            self.add_item(
                title="Mark as read",
                subtitle='Mark notification as read.',
                method=self.mark_read,
                parameters=[id],
            )
            self.add_item(
                title="Mark all as read",
                subtitle='Mark all notifications as read.',
                method=self.clear_all,
            )
        finally:
            self.add_item(
                title="Refresh Cache",
                subtitle='Refresh the cache.',
                method=self.refresh_cache
            )


    def cache_remove_result(self, id):
        if utils.cache_path('gh.json').exists():
            with open(utils.cache_path('gh.json'), 'r') as f:
                cache = json.load(f)
            for result in cache:
                if result['ContextData'][0] == id:
                    cache.remove(result)
                    with open(utils.cache_path('gh.json'), 'w') as f:
                        json.dump(cache, f)

    def mark_read(self, id):
        self._init_github()
        self.gh.get_user().get_notification(id).mark_as_read()
        self.cache_remove_result(id)
        self.change_query(self.query, True)

    def refresh_cache(self):
        utils.remove_cache('gh.json')

    def clear_all(self):
        self._init_github()
        notifications = self.gh.get_user().get_notifications()
        for notification in notifications:
            notification.mark_as_read()
            self.cache_remove_result(notification.id)

    def open_url(self, url, id):
        self._init_github()
        self.gh.get_user().get_notification(id).mark_as_read()
        self.cache_remove_result(id)
        webbrowser.open(url)

if __name__ == "__main__":
    GithubNotifications()
