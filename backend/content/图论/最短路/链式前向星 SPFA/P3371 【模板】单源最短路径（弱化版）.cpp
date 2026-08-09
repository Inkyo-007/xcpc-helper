#include<bits/stdc++.h>
#define inf 0x3f3f3f3f
#define maxn 500005
#define endl '\n'
#define ll long long
using namespace std;

int n, m;
int head[maxn], nxt[maxn], to[maxn], val[maxn], cnt;
bool vis[maxn];
int dis[maxn];
queue <int> q;

void add_edge(int u, int v, int w)
{
	nxt[++ cnt] = head[u];
	head[u] = cnt;
	to[cnt] = v;
	val[cnt] = w;
}

void spfa(int s)
{
	q.push(s);
	dis[s] = 0;
	while(q.size())
	{
		int u = q.front(); q.pop();
		vis[u] = false;
		for(int i = head[u]; i; i = nxt[i])
		{
			int v = to[i], w = val[i];
			if(dis[v] > dis[u] + w)
			{
				dis[v] = dis[u] + w;
				if(!vis[v])
				{
					q.push(v);
					vis[v] = true;
				}
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
	spfa(s);
	for(int i = 1; i <= n; i ++) 
	{
		if(dis[i] == inf) cout << 2147483647 << ' ';
		else cout << dis[i] << ' ';
	}
	
	return 0;
} 