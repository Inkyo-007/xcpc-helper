#include<bits/stdc++.h>
#define inf 0x3f3f3f3f
#define maxn 200005
#define endl '\n'
#define ll long long
using namespace std;

int n, m;
int head[maxn], nxt[maxn], to[maxn], val[maxn], cnt;
bool vis[maxn];
int dis[maxn];
priority_queue <pair<int, int> > q;

void add_edge(int u, int v, int w)
{
	nxt[++ cnt] = head[u];
	head[u] = cnt;
	to[cnt] = v;
	val[cnt] = w;
}

void dij(int s)
{
	q.push(make_pair(0, s));
	dis[s] = 0;
	while(q.size())
	{
		int u = q.top().second; q.pop();
		if(vis[u]) continue;
		vis[u] = true;
		for(int i = head[u]; i; i = nxt[i])
		{
			int v = to[i], w = val[i];
			if(dis[v] > dis[u] + w)
			{
				dis[v] = dis[u] + w;
				q.push(make_pair(-dis[v], v));
			}
		}
	}
}

int main()
{
	ios::sync_with_stdio(false);
	cin.tie(0); cout.tie(0);
	
	memset(dis, inf, sizeof(dis));
	int s;
	cin >> n >> m >> s;
	for(int i = 1; i <= m; i ++)
	{
		int u, v, w; cin >> u >> v >> w;
		add_edge(u, v, w);
	}
	dij(s);
	for(int i = 1; i <= n; i ++) cout << dis[i] << ' ';
	
	return 0;
}
