Create a Python script to perform the following tasks:

1. Create 100 users via the register_user endpoint.

2. Fetch a random user from the database (let’s call them the main user), log in as this user via the login endpoint using their database ID and the password 12345.

3. Add 20 random friends to this user via the add_friend endpoint.

4. The added friends must log in (using their database IDs and the password 12345) and each create 40 short posts (just one sentence each) via the create_post endpoint.

5. For the main user, fetch their friends' feed via the get_friends_feed endpoint, display the number of posts, measure the execution time of the feed request, and print the oldest post in the feed (remember it).

6. One of the friends should generate 100 more posts (via create_post) so that the total number of posts in the main user’s feed exceeds 1,000, triggering cache invalidation—this should result in the oldest posts being purged.

7. Fetch the friends' feed again for the main user via the same endpoint, display the number of posts, measure the execution time, and print the oldest post (remember it). Verify that the oldest post is now different.

8. Randomly select another user from the database (let’s call them the new friend), who is not currently a friend of the main user, and log in as them (using their ID and password 12345).

9. Generate 100 posts for the new friend (via create_post).

10 Add the new friend to the main user via add_friend.

11. Fetch the friends' feed once more for the main user via the same endpoint, display the number of posts, and measure the execution time. Ensure that posts from the new friend now appear in the feed.

12. Document all test stages with results in an HTML report (in Russian).

