class DirectedEulerPath { //有向图点序列欧拉路径，点序列字典序最小
public:
	DirectedEulerPath(int n) : n(n), graph(n + 1), in_deg(n + 1), out_deg(n + 1) {}
	
	void addEdge(int u, int v) {
		graph[u].push_back(v);
		out_deg[u]++;
		in_deg[v]++;
	}
	
	vector<int> findEulerPath() {
		// 为了字典序最小，先排序邻接表
		for (int i = 1; i <= n; ++i)
			sort(graph[i].rbegin(), graph[i].rend()); // 逆序堆栈式 dfs
		
		int start = -1, end = -1;
		for (int i = 1; i <= n; ++i) {
			if (out_deg[i] == in_deg[i] + 1) {
				if (start == -1) start = i;
				else return {}; // 多于一个起点
			} else if (in_deg[i] == out_deg[i] + 1) {
				if (end == -1) end = i;
				else return {}; // 多于一个终点
			} else if (in_deg[i] != out_deg[i]) {
				return {};
			}
		}
		
		if (start == -1) {
			for (int i = 1; i <= n; ++i) {
				if (!graph[i].empty()) {
					start = i;
					break;
				}
			}
		}
		
		if (start == -1) return {}; // 没有边
		
		dfs(start);
		reverse(path.begin(), path.end());
		
		// 检查是否使用了所有边
		int total_edges = accumulate(out_deg.begin(), out_deg.end(), 0);
		if ((int)path.size() != total_edges + 1)
			return {};
		
		return path;
	}
	
private:
	int n;
	vector<vector<int>> graph;
	vector<int> in_deg, out_deg;
	vector<int> path;
	
	void dfs(int u) {
		while (!graph[u].empty()) {
			int v = graph[u].back();
			graph[u].pop_back();
			dfs(v);
		}
		path.push_back(u);
	}
};