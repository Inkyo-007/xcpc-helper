/** ECharts 按需注册：只打包柱状图所需模块（热力图已改为 DOM 网格，
 * 见 components/ActivityHeatmap.vue 与 model/heatmap-grid.ts）。
 */

import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([BarChart, GridComponent, TooltipComponent, SVGRenderer])

export { echarts }
export type { EChartsCoreOption } from 'echarts/core'
