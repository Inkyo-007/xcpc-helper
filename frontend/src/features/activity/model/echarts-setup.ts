/** ECharts 按需注册：只打包本功能所需模块（柱状图 + 技能树旭日图 + 分析页饼图/图例；
 * 热力图已改为 DOM 网格，见 components/ActivityHeatmap.vue 与 model/heatmap-grid.ts）。
 * Title 供 verdict 环形饼图在中心显示总提交数。
 */

import { BarChart, PieChart, SunburstChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  PieChart,
  SunburstChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  SVGRenderer,
])

export { echarts }
export type { EChartsCoreOption } from 'echarts/core'
